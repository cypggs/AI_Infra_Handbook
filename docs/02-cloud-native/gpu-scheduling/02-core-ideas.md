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
| **vGPU** | 由 hypervisor/软件虚拟化 | 可配置 | 可配置 | 私有云/桌面虚拟化 | 通常配合 KubeVirt 等 |

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
| v1.36 PodGroup（原生） | 默认 scheduler 原生 | PodGroup API | 未来可能统一 |

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

## 2.7 与 K8s 其他组件的边界

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
├── kubelet TopologyManager
│      └── 节点级 NUMA/PCIe 对齐
└── 可观测（DCGM-Exporter / GFD / Prometheus）
       └── 把 GPU 健康、利用率、拓扑暴露给调度与监控
```

关键边界：

- **Device Plugin ≠ scheduler**：Device Plugin 发现设备并分配给容器，不参与“选哪个节点”。
- **scheduler-plugins ≠ Volcano**：前者运行在默认调度器内，后者替换整个调度器；前者适合补充能力，后者适合批处理/AI 专属集群。
- **Kueue ≠ scheduler**：Kueue 决定“这个 Job 现在能不能进调度器”，scheduler 决定“这个 Pod 落在哪个节点”。
- **GPU Operator ≠ Device Plugin**：GPU Operator 管理 Device Plugin 的生命周期，还包括驱动、container-toolkit、MIG 等。

## 2.8 本章小结

| 概念 | 一句话 |
|---|---|
| Extended Resource | 把 GPU 变成 K8s 可识别的 `nvidia.com/gpu` |
| 整卡独占 | 最简单、最可预测的 GPU 使用方式 |
| MIG | 硬件级切分，显存与计算硬隔离 |
| MPS | 多进程共享一张卡，显存不隔离 |
| Time-slicing | 时间片共享，适合低负载/开发 |
| Device Plugin | kubelet 与 GPU 之间的标准 gRPC 接口 |
| 拓扑感知 | 把 NUMA/PCIe/NVLink 纳入调度决策 |
| Gang 调度 | 一组 Pod 同时满足才调度 |
| 队列调度 | 资源不足时排队、配额、公平共享 |

理解了这些概念，下一章我们把它们放到 K8s 集群里，看 GPU 调度架构的全景与组件协作。
