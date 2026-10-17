# 2. 核心思想

> 一句话理解：**GPU 调度的核心思想是“把物理 GPU 的异构能力翻译成 K8s 可调度、可切分、可观测的资源语义”**——从 `nvidia.com/gpu` 的整数卡，到 MIG/MPS/time-slicing 的软/硬切分，再到拓扑与 Gang 约束，平台工程师是在用 K8s 的扩展机制为 AI 负载重新建模资源。

## 2.1 Extended Resource：让 K8s 认识 GPU

Kubernetes 通过 **extended resource** 机制允许外部系统向节点申报任意资源。NVIDIA Device Plugin 启动后，会更新节点的 `status.allocatable`：

```yaml
status:
  allocatable:
    cpu: "64"
    memory: 256Gi
    nvidia.com/gpu: "8"
  capacity:
    nvidia.com/gpu: "8"
```

用户在 Pod 里这样声明：

```yaml
resources:
  limits:
    nvidia.com/gpu: "2"
  requests:
    nvidia.com/gpu: "2"
```

scheduler 在 Filter 阶段会检查节点 `allocatable` 是否满足请求；在 Score 阶段可以按剩余资源打分。但 extended resource 有几个天然限制：

1. **只有数量，没有属性**：`nvidia.com/gpu` 是一张卡，但 scheduler 不知道它是 A100 80GB 还是 A10 24GB，不知道它在哪个 NUMA、有没有 NVLink。
2. **只减不增**：Device Plugin 上报后，scheduler 按整数递减；没有内置的“显存余量”概念。
3. **分配发生在绑定之后**：scheduler 选好节点，kubelet 在启动容器时才调用 Device Plugin Allocate。如果此时卡坏了，Pod 会报 `UnexpectedAdmissionError`。

因此，extended resource 只是起点。真正的 GPU 调度需要在它之上叠加切分、拓扑、队列等语义。

## 2.2 GPU 切分模型对比

AI 平台要回答一个核心问题：**一张卡给几个 Pod 用？怎么隔离？**

| 模型 | 切分粒度 | 显存隔离 | 计算隔离 | 适用场景 | K8s 暴露方式 |
|---|---|---|---|---|---|
| **整卡（Exclusive）** | 1 张物理卡 | 完全隔离 | 完全隔离 | 训练、大模型推理 | `nvidia.com/gpu: 1` |
| **MIG** | 1 张物理卡 → 最多 7 个实例 | 硬隔离 | 硬隔离（compute instance） | 多租户、显存可预测 | `nvidia.com/mig-3g.40gb` 等 |
| **MPS** | 多进程共享一张卡 | 不隔离（共享显存池） | 软隔离（上下文共享） | 小模型高密度推理 | 同一 `nvidia.com/gpu` 多个 Pod |
| **Time-slicing** | 多个容器轮流使用一张卡 | 不隔离 | 不隔离（时间片） | 极低负载共享、开发测试 | Device Plugin ConfigMap |
| **Fractional GPU（显存/算力配额）** | 按显存 MB 与算力百分比切分 | 软隔离（由拦截层强制） | 软隔离（时间片 + 配额） | 中小模型混部、超卖场景 | HAMi `vgpu` 资源 / KAI Scheduler GPU fraction |
| **vGPU** | 由 hypervisor/软件虚拟化 | 可配置 | 可配置 | 私有云/桌面虚拟化 | 通常配合 KubeVirt 等 |

> **2025-2026 新动态**：KAI Scheduler 的 fractional GPU 共享底层采用了 HAMi-core 设备拦截层，把“显存超限即失败”的软共享升级为**硬隔离级**的显存配额（进程申请显存超额会被直接拒绝）；DRA 侧则通过 Consumable Capacity（KEP-5075，1.37 Beta）把“显存/算力分数化申请”做进原生资源模型。

### 整卡独占

最简单、最常用。Pod 拿到整张卡，不与其他 Pod 共享。优点是可预测、无干扰；缺点是利用率可能低，尤其在推理小模型时。

### MIG（Multi-Instance GPU）

NVIDIA Ampere/Hopper 及以后架构支持。一张 A100 80GB 可以被切成例如：

```text
A100 80GB
├── mig-1g.10gb  x 7
├── mig-2g.20gb  x 3
├── mig-3g.40gb  x 2
└── mig-7g.80gb  x 1
```

每个 MIG 实例有独立的显存和计算资源，从 K8s 角度看就像一张“小卡”。Device Plugin 在 MIG 模式下会暴露 `nvidia.com/mig-1g.10gb` 等资源名，而不是 `nvidia.com/gpu`。

### MPS（Multi-Process Service）

MPS 允许多个 CUDA 进程共享同一张 GPU，减少上下文切换开销。但它**不隔离显存**，一个进程 OOM 会影响其他进程。适合显存需求可控、对延迟不敏感的小模型推理。

### Time-slicing

NVIDIA Device Plugin 提供的一种“超卖”机制。多个 Pod 共享一张卡，GPU 驱动在它们之间快速切换上下文。它的隔离性比 MPS 更弱，适合开发测试或几乎不会同时满载的场景。

### 选型建议

| 场景 | 推荐模型 | 理由 |
|---|---|---|
| 大模型训练 | 整卡独占 | 可预测、NCCL 性能最好 |
| 多租户推理 | MIG | 硬隔离，显存可配额 |
| 中小模型高密度混部 | Fractional GPU（HAMi / KAI） | 显存配额硬限制，比 MPS/time-slicing 更安全 |
| 小模型高密度推理 | MPS | 低上下文开销，但需要控制显存 |
| 开发/测试/低负载 | time-slicing | 最大化卡利用率，接受性能波动 |

## 2.3 Device Plugin 抽象

Device Plugin 是 K8s 与异构硬件之间的标准接口。它向 kubelet 注册，并通过 gRPC 提供三个核心能力：

```text
kubelet device-plugin-manager
       │
       ├─ Register(DevicePluginEndpoint, ResourceName)
       │
       ├─ ListAndWatch(Empty) → stream ListAndWatchResponse
       │      持续上报设备列表与健康状态
       │
       └─ Allocate(AllocateRequest) → AllocateResponse
              为容器分配设备，返回设备节点、环境变量、挂载点
```

### 注册与发现

Device Plugin 启动后，会在 `/var/lib/kubelet/device-plugins/` 下创建一个 Unix socket，并调用 kubelet 的 `Register` RPC：

```protobuf
service Registration {
  rpc Register(RegisterRequest) returns (Empty);
}

message RegisterRequest {
  string version = 1;
  string endpoint = 2;
  string resource_name = 3;  // 例如 nvidia.com/gpu
}
```

kubelet 验证后，把该资源名加入节点的 `allocatable`。

### ListAndWatch

Device Plugin 持续向 kubelet 推送设备列表：

```protobuf
message ListAndWatchResponse {
  repeated Device devices = 1;
}

message Device {
  string ID = 1;
  string health = 2;  // Healthy / Unhealthy
}
```

当某张卡发生 Xid 错误、温度异常或被 MIG 重新配置时，Device Plugin 会把它标记为 `Unhealthy`。kubelet 会把该设备从 `allocatable` 中移除，已分配的 Pod 视策略可能被驱逐或不再接受新 Pod。

### Allocate

容器启动前，kubelet 调用 `Allocate`：

```protobuf
message AllocateRequest {
  repeated ContainerAllocateRequests container_requests = 1;
}

message ContainerAllocateRequests {
  repeated string devicesIDs = 1;
}
```

Device Plugin 返回：

```protobuf
message ContainerAllocateResponse {
  map<string, string> envs = 1;
  repeated Mount mounts = 2;
  repeated DeviceSpec devices = 3;
}
```

NVIDIA Device Plugin 典型返回：

- `NVIDIA_VISIBLE_DEVICES=GPU-xxx,GPU-yyy`（容器可见 GPU UUID）。
- `/dev/nvidia0`、`/dev/nvidia1` 等字符设备。
- `/dev/nvidiactl`、`/dev/nvidia-uvm` 等控制设备。
- CUDA 库挂载（可选，取决于 container-toolkit 配置）。

### PreStartContainer

部分 Device Plugin 实现了 `PreStartContainer`，在容器启动前做额外设置，例如 MIG 实例配置检查。

## 2.4 拓扑感知调度

### 为什么需要拓扑

两个都请求 4 卡的 Pod，落在同一节点上可能千差万别：

| 分配方式 | NVLink 亲和 | 性能 |
|---|---|---|
| 4 张卡在同一 NVSwitch 下 | 是 | 最高 |
| 4 张卡跨两个 NVSwitch | 部分 P2P 需经 PCIe | 下降 |
| 4 张卡跨 NUMA | CPU/GPU 拷贝路径长 | 显著下降 |

拓扑感知调度需要两类信息：

1. **节点拓扑**：NUMA、PCIe、NIC、GPU 的相对位置，由 Node Feature Discovery（NFD）和 GPU Feature Discovery（GFD）生成标签或 CR。
2. **Pod 拓扑偏好**：用户声明“希望 GPU 在同一 NUMA”或“需要 NVLink 亲和”。

### NodeResourceTopology

`scheduler-plugins` 的 `NodeResourceTopology` 插件读取 `NodeResourceTopology` CR（由 topology-exporter 生成），在 Filter/Score 阶段使用：

```yaml
apiVersion: topology.node.k8s.io/v1alpha2
kind: NodeResourceTopology
metadata:
  name: node-1
zones:
  - name: node-0
    type: Node
    resources:
      nvidia.com/gpu: "4"
  - name: node-1
    type: Node
    resources:
      nvidia.com/gpu: "4"
```

在更细粒度实现中，zones 可以表示 NUMA node、PCIe switch 或 NVSwitch domain。

### Topology Manager

kubelet 内部的 `TopologyManager` 负责**节点级**拓扑对齐。它会在 CPU、内存、设备之间协调，确保 Pod 的资源分配满足 `topologyManagerPolicy`：

```yaml
kubeletConfig:
  topologyManagerPolicy: single-numa-node
  topologyManagerScope: pod
```

- `single-numa-node`：要求 Pod 的所有资源来自同一 NUMA node，否则拒绝 admission。
- `restricted`：尽量对齐，不对齐时仍允许。
- `best-effort`：尽量对齐，无强制要求。

Topology Manager 与 Device Plugin 的交互点是 `GetPreferredAllocation`：Device Plugin 可以告诉 kubelet“优先选哪些设备组合”以满足拓扑。

## 2.5 Gang all-or-nothing 调度

Gang 调度的语义是：一个 Job 的所有必需 Pod 同时就绪，才允许它们被调度；否则全部保持在 Pending。

### 为什么不用默认调度器

默认调度器是 Pod 级的：每个 Pod 独立调度。对于 8 卡训练 Job，它可能先调度 6 个，后 2 个没资源。这 6 个已经启动的 Pod 会占着资源等待，造成死锁或浪费。

### PodGroup

Gang 调度通常引入 `PodGroup` 概念：

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: llm-training
spec:
  minMember: 8
  minResources:
    nvidia.com/gpu: 8
  queue: default
```

Pod 通过 `scheduling.volcano.sh/podgroup-name: llm-training` 关联到 PodGroup。scheduler 会检查：当前集群是否能同时满足 PodGroup 的 `minMember` 和 `minResources`。能，则一次性调度；不能，则全部等待。

### 实现方案对比

| 方案 | 位置 | Gang 语义 | 其他能力 |
|---|---|---|---|
| scheduler-plugins Coscheduling | 默认 scheduler 插件 | PodGroup CRD | 兼容默认调度器 |
| Volcano | 独立调度器 | Job/PodGroup | 队列、抢占、作业管理 |
| Kueue | 独立 controller + 准入 | Workload/PodSet | 队列、公平共享、抢占 |
| KAI Scheduler | 独立调度器（CNCF Sandbox，基于 kube-batch） | PodGroup / 层级 PodGroup | 队列层级、fractional GPU、TAS、抢占 |
| v1.37 原生 PodGroup（KEP-4671，Beta） | 默认 scheduler 原生 | Workload API + PodGroup，opt-in | 配套 workload-aware 抢占与 PodGroup 排队，防 livelock |

> **1.37 原生 Gang 调度要点**：Kubernetes 1.37（2026-08）把 KEP-4671 推进到 Beta——调度器只有在**集群容量能覆盖整个 PodGroup 时**才提交该组，而不是先占一部分卡再等；配套的两块是 **workload-aware preemption**（不会为了一个无法推进的抢占者去驱逐正在运行的 Job）和 **PodGroup queueing**（防止多个大 Job 相互 livelock）。默认不启用，需要显式创建 Workload/PodGroup 对象。短期内外部调度器（Volcano/Kueue/KAI）仍提供队列、公平共享等更完整的多租户语义，原生 API 的价值在于统一各调度器的底层语义。

## 2.6 队列公平调度

队列调度的目标是：在资源不足时，不直接失败，而是把请求按规则排队；在资源释放时，按优先级、公平性、借用规则发放。

### Kueue 模型

```text
ClusterQueue（全局资源池）
   └── LocalQueue（命名空间级队列）
        └── Workload（由 Job/Deployment 转化而来）
```

- **ClusterQueue**：定义配额（quota）、借用限制（lendingLimit）、公平共享权重。
- **LocalQueue**：命名空间内的入口，绑定到某个 ClusterQueue。
- **Workload**：Kueue 自动把 Job、Deployment、StatefulSet 等Workload化。

Kueue 在准入（admission）阶段决定一个 Workload 是否能获得资源；获得后，它才允许原对象继续被调度器处理。

### Volcano 模型

Volcano 的 `Queue` 是调度器的内置概念：

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: training
spec:
  weight: 1
  capability:
    cpu: "1000"
    memory: 2000Gi
    nvidia.com/gpu: "64"
```

`weight` 决定多个队列之间的资源分配比例；`capability` 是硬上限。Volcano scheduler 还会做 **reclaim**（回收）和 **preempt**（抢占）。

### 公平共享

Kueue 的 `fairSharing` 允许定义权重，确保小团队不被大团队饿死：

```yaml
spec:
  fairSharing:
    weight: 100
```

当多个 ClusterQueue 竞争时，系统按权重比例分配可用资源，而不是谁先到谁先得。

### KAI Scheduler：把队列与 fraction 统一进一个调度器

KAI Scheduler（NVIDIA 2025-04 开源，源自 Run:ai 调度引擎，2025-12 进入 CNCF Sandbox）把上面几件事合进一个独立调度器：

```text
Queue（层级队列：配额 / 权重 / 借用限制）
   └── PodGroup（Gang + 层级 PodGroup，支持 PD 分离等复合负载）
         └── GPU 分配策略：整卡 / MIG / fraction（显存+算力配额）
```

它与 Kueue 的关键差异：Kueue 是“控制平面准入 + 原生调度器执行”的两段式，KAI 是“独立调度器一步到位”，并且**原生支持 fractional GPU**（配合 HAMi-core 拦截层做显存硬配额）与层级 TAS（Topology Aware Scheduling）。

### 推理调度新范式：从“占卡”到“PD 分离 + 感知路由”

2026 年推理场景的调度粒度从“Pod 占几张卡”细化到“请求该去哪个 Pod”：

- **PD 分离（Prefill/Decode Disaggregation）**：把计算密集的 prefill 与显存密集的 decode 拆到不同 Pod，分别扩缩容；要求调度器能把两类 Pod 各自 Gang 起来并感知 KV Cache 位置——llm-d（CNCF，KubeCon EU 2026 由 IBM Research / Red Hat / Google Cloud 捐赠）把这一模式做成 K8s 原生框架。
- **请求级路由**：llm-d 的 routing 组件按 KV Cache 亲和性把请求路由到持有对应前缀缓存的 decode Pod，显著降低 TTFT。
- **多节点推理**：GB200 NVL72 这类机柜级 NVLink 域让跨节点张量并行成为常态，调度需要理解 ComputeDomain / 整柜拓扑（见 2.7 DRA）。

## 2.7 DRA：从 Device Plugin 到声明式设备分配

### Device Plugin 的三条天花板

Device Plugin 模型（1.14 GA 至今）有三大结构性限制，DRA（Dynamic Resource Allocation，1.26 alpha、**1.34 GA**）就是为突破它们而设计：

1. **只有数量，没有属性**：scheduler 只能问“还有没有 `nvidia.com/gpu`”，不能问“有没有显存 ≥ 80GB 且与同 NUMA NIC 亲和的 GPU”。
2. **分配决策在节点**：scheduler 选节点，设备实际分配发生在 kubelet 调 `Allocate` 时——选卡和用卡分离，拓扑优化只能靠 `GetPreferredAllocation` 事后补救。
3. **无法表达复杂拓扑**：多机 NVLink（GB200 NVL72）、MIG 动态分区这类“设备组合”语义，Device Plugin 表达不了。

### DRA 的核心对象

```yaml
apiVersion: resource.k8s.io/v1
kind: DeviceClass          # 管理员定义“一类设备”长什么样
metadata:
  name: gpu-h100-nvlink
spec:
  selectors:
    - cel:
        expression: |
          device.attributes["nvidia.com"].product == "H100"
          && device.attributes["resource.kubernetes.io/numaNode"] == 0
---
apiVersion: resource.k8s.io/v1
kind: ResourceClaim        # 工作负载声明“我要一个这样的设备”
metadata:
  name: llm-train-gpu
spec:
  devices:
    requests:
      - name: gpu
        deviceClassName: gpu-h100-nvlink
        count: 8
```

| 对象 | 作用 | 谁创建 |
|---|---|---|
| `DeviceClass` | 定义设备选择规则（CEL 表达式按属性过滤） | 集群管理员 |
| `ResourceSlice` | DRA driver 上报设备清单与属性（型号、显存、NUMA、健康） | DRA driver |
| `ResourceClaim` / `ResourceClaimTemplate` | 工作负载的设备需求声明 | 用户 / 工作负载模板 |
| `ResourceClaim` status | driver 回填分配结果（设备 ID、网络接口信息） | DRA driver |

### 版本演进（截至 2026-10，K8s 1.37）

| 版本 | DRA 里程碑 |
|---|---|
| 1.34（2025-09） | 核心 API（resource.k8s.io/v1）**GA**；Consumable Capacity（显存/算力分数化）发布；Pod 状态可上报 DRA 设备健康 |
| 1.35（2025-12） | 特性门锁定常开；扩展资源映射（KEP-5004）alpha |
| 1.36（2026-04） | 分区设备（KEP-4815）与设备污点（KEP-5055）beta；优先级列表稳定 |
| 1.37（2026-08） | **扩展资源映射 GA**：DeviceClass 直接声明 `extendedResourceName: nvidia.com/gpu`，Pod 侧无需任何 ResourceClaim 改造；设备污点/容忍 GA（单卡故障打污点即可，不必 drain 整节点）；ResourceClaim 设备状态 GA；Workload 直接引用 ResourceClaim（KEP-5729 beta，一个 Claim 供整个 PodGroup 共享） |

### 扩展资源映射：迁移的桥

1.37 GA 的扩展资源映射是 Device Plugin 平滑迁移到 DRA 的关键：DeviceClass 上声明 `extendedResourceName` 后，**原有只写 `limits: nvidia.com/gpu: 1` 的 Pod 不需要任何改动**，就由 DRA driver 来接管分配：

```yaml
apiVersion: resource.k8s.io/v1
kind: DeviceClass
metadata:
  name: nvidia-gpu
spec:
  extendedResourceName: nvidia.com/gpu   # 1.37 GA：Pod spec 保持原样
```

这意味着平台可以把调度基础设施切到 DRA（获得属性选择、设备污点、拓扑感知），而用户侧 YAML 完全无感。

### NVIDIA DRA Driver 与 GPU Operator 26.x

NVIDIA 的 `dra-driver-nvidia-gpu` 于 KubeCon EU 2026 捐入 kubernetes-sigs（Apache-2.0），当前 v0.5.x（2026-08）。需要注意成熟度分层：

- **ComputeDomain（多机 NVLink，GB200 NVL72）**：官方支持，用于整柜级 GPU 组合分配。
- **GPU kubelet plugin（整卡/MIG 细粒度分配）**：alpha，Helm 默认关闭（`gpuResourcesEnabledOverride=true` 才启用），生产上 Device Plugin 仍是更稳的选择。

GPU Operator 从 **26.7** 起把 DRA 纳入编排：新增 `GPUCluster` CR 统一管理 DRA driver、ComputeDomain、DCGM 与校验任务，要求 K8s ≥ 1.34.2、驱动 ≥ 580、CDI 兼容的容器运行时。

## 2.8 与 K8s 其他组件的边界

```text
K8s 生态
├── kube-scheduler
│      └── 负责节点级决策：Filter / Score / Bind
├── Device Plugin
│      └── 负责设备级发现与分配：ListAndWatch / Allocate
├── GPU Operator
│      └── 负责节点组件生命周期：driver / toolkit / plugin / exporter
├── scheduler-plugins
│      └── 在默认调度器内扩展 Gang / 拓扑 / 弹性配额
├── Volcano
│      └── 独立批处理调度器：Job / PodGroup / Queue / 抢占
├── Kueue
│      └── 控制平面队列：ClusterQueue / LocalQueue / Workload
├── DRA（1.34 GA）
│      └── 声明式设备分配：DeviceClass / ResourceClaim / ResourceSlice
├── KAI Scheduler（CNCF Sandbox）
│      └── GPU 一体化调度：Gang / 层级队列 / fraction / TAS
├── kubelet TopologyManager
│      └── 节点级 NUMA/PCIe 对齐
└── 可观测（DCGM-Exporter / GFD / Prometheus）
       └── 把 GPU 健康、利用率、拓扑暴露给调度与监控
```

关键边界：

- **Device Plugin ≠ scheduler**：Device Plugin 发现设备并分配给容器，不参与“选哪个节点”。
- **DRA ≠ Device Plugin 的简单替代**：DRA 把“选哪台设备”的决策从 kubelet 提前到 scheduler（调度器直接为 ResourceClaim 选设备），并引入属性/污点/拓扑语义；1.37 起两者可通过扩展资源映射共存过渡。
- **scheduler-plugins ≠ Volcano/KAI**：前者运行在默认调度器内，后两者替换整个调度器；前者适合补充能力，后者适合 AI 专属集群。
- **Kueue ≠ scheduler**：Kueue 决定“这个 Job 现在能不能进调度器”，scheduler 决定“这个 Pod 落在哪个节点”。
- **GPU Operator ≠ Device Plugin**：GPU Operator 管理 Device Plugin 的生命周期，还包括驱动、container-toolkit、MIG、以及 26.7 起的 DRA driver。

## 2.9 本章小结

| 概念 | 一句话 |
|---|---|
| Extended Resource | 把 GPU 变成 K8s 可识别的 `nvidia.com/gpu` |
| 整卡独占 | 最简单、最可预测的 GPU 使用方式 |
| MIG | 硬件级切分，显存与计算硬隔离 |
| MPS | 多进程共享一张卡，显存不隔离 |
| Time-slicing | 时间片共享，适合低负载/开发 |
| Fractional GPU | 显存/算力配额化共享（HAMi-core / KAI），介于 MIG 与 MPS 之间 |
| Device Plugin | kubelet 与 GPU 之间的标准 gRPC 接口 |
| DRA | 声明式设备分配（1.34 GA），按属性选设备、设备污点、扩展资源映射 |
| 拓扑感知 | 把 NUMA/PCIe/NVLink 纳入调度决策 |
| Gang 调度 | 一组 Pod 同时满足才调度（1.37 起 K8s 原生 Beta） |
| 队列调度 | 资源不足时排队、配额、公平共享 |

理解了这些概念，下一章我们把它们放到 K8s 集群里，看 GPU 调度架构的全景与组件协作。
