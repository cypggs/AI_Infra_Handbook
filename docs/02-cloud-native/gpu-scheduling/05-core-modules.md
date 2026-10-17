# 5. 核心模块

> 一句话理解：**GPU 调度不是“一个调度器”的事，而是 Device Plugin / DRA、GPU Operator、scheduler-plugins / Volcano / Kueue / KAI、拓扑发现、可观测、推理流量层（llm-d）七大模块的协奏曲**——每个模块解决一个特定子问题，拼在一起才构成生产级 GPU 集群。

## 5.1 NVIDIA Device Plugin

NVIDIA Device Plugin 是 K8s 与 GPU 之间的“翻译器”：它把物理 GPU 翻译成 `nvidia.com/gpu` 这种 K8s 能理解的扩展资源。

### gRPC 接口

Device Plugin 需要实现 K8s 定义的 `DevicePlugin` gRPC 服务：

| 方法 | 调用方 | 作用 |
|---|---|---|
| `GetDevicePluginOptions` | kubelet | 返回设备插件选项（如是否支持预启动） |
| `ListAndWatch` | kubelet | 流式返回所有设备及其健康状态 |
| `Allocate` | kubelet | Pod 绑定到节点后，为容器分配具体设备 |
| `PreStartContainer` | kubelet | 容器启动前做最后配置（如设置 CUDA 可见性） |
| `GetPreferredAllocation` | kubelet | 让插件参与设备选择决策（可选） |

### 注册流程

```text
Device Plugin Pod 启动
   │
   ▼
监听 /var/lib/kubelet/device-plugins/nvidia-gpu.sock
   │
   ▼
调用 kubelet Registration service
   { endpoint="nvidia-gpu.sock", resource_name="nvidia.com/gpu" }
   │
   ▼
kubelet 连接 socket，验证 ListAndWatch 返回的设备列表
   │
   ▼
更新 node.status.allocatable.nvidia.com/gpu
```

### 共享 GPU 配置

Device Plugin 通过 ConfigMap 开启 MPS 或 time-slicing：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: device-plugin-config
data:
  config: |
    {
      "sharing": {
        "timeSlicing": {
          "renameByDefault": false,
          "failRequestsGreaterThanOne": false,
          "resources": [
            {"name": "nvidia.com/gpu", "replicas": 4}
          ]
        }
      }
    }
```

开启后，一张物理卡会被重命名为 `nvidia.com/gpu` 的 4 个“副本”，多个 Pod 可以请求这些副本并分时复用同一张卡。

> **定位变化（2026）**：DRA 1.34 GA、扩展资源映射 1.37 GA 之后，Device Plugin 仍是生产最稳的设备分配路径，但长期看 NVIDIA 会把细粒度分配能力逐步迁移到 DRA driver（GPU kubelet plugin 目前 alpha，默认关闭）。规划新集群时建议：短期继续 Device Plugin，同时让 GPU Operator ≥ 26.7 就绪以便平滑切换。

## 5.2 NVIDIA GPU Operator

GPU Operator 把节点上所有 GPU 相关组件打包成 Operator，自动化安装、升级、验证。

### ClusterPolicy CR

```yaml
apiVersion: nvidia.com/v1
kind: ClusterPolicy
metadata:
  name: cluster-policy
spec:
  driver:
    enabled: true
  toolkit:
    enabled: true
  devicePlugin:
    enabled: true
    config:
      name: device-plugin-config
  dcgmExporter:
    enabled: true
  gfd:
    enabled: true
  migManager:
    enabled: true
  nodeStatusExporter:
    enabled: true
  validator:
    enabled: true
```

### 组件清单

| 组件 | 形态 | 关键职责 |
|---|---|---|
| NVIDIA Driver DaemonSet | DaemonSet | 编译/加载内核驱动 |
| NVIDIA Container Toolkit | DaemonSet | 让 runtime 识别 `NVIDIA_VISIBLE_DEVICES` |
| NVIDIA Device Plugin | DaemonSet | 上报 `nvidia.com/gpu`，处理 Allocate |
| DCGM-Exporter | DaemonSet | 暴露 GPU 利用率、显存、温度、Xid 等指标 |
| GPU Feature Discovery | DaemonSet | 给节点打 GPU 型号/显存/MIG 标签 |
| MIG Manager | DaemonSet | 按 ConfigMap 自动切分/重置 MIG profile |
| Node Status Exporter | DaemonSet | 把节点 GPU 状态写回 CR 或 metrics |
| Validator | DaemonSet/Job | 校验各组件就绪状态 |

### 节点就绪状态机

```text
NotReady
   │
   ▼
DriverInstalling → DriverReady
   │
   ▼
ToolkitInstalling → ToolkitReady
   │
   ▼
DevicePluginInstalling → DevicePluginReady
   │
   ▼
MIGConfiguring → MIGReady
   │
   ▼
DCGMInstalling → Ready
```

只有状态变为 `Ready` 后，scheduler 才会把 GPU Pod 调度到该节点。新 GPU 节点加入集群后通常需要几分钟完成这个流水线。

## 5.3 scheduler-plugins

scheduler-plugins 是一组运行在 kube-scheduler 内部的扩展插件，适合“不想换调度器，只想补能力”的集群。

### Coscheduling（Gang 调度）

核心对象：`PodGroup`。

```yaml
apiVersion: scheduling.x-k8s.io/v1alpha1
kind: PodGroup
metadata:
  name: train-pg
spec:
  scheduleTimeoutSeconds: 120
  minMember: 4
```

Pod 通过 `scheduling.x-k8s.io/pod-group` annotation 加入组：

```yaml
metadata:
  annotations:
    scheduling.x-k8s.io/pod-group: |
      {"name": "train-pg", "minMember": 4}
```

实现要点：

- `QueueSort`：按 PodGroup 创建时间排序。
- `PreFilter`：检查 PodGroup 是否已超时。
- `Reserve`：为 Pod 在假定节点上预留资源。
- `Permit`：等待组内所有成员都完成 Reserve；若到齐则放行，否则进入等待状态。

### NodeResourceTopology（拓扑感知）

读取 `NodeResourceTopology` CR：

```yaml
apiVersion: topology.node.k8s.io/v1alpha2
kind: NodeResourceTopology
metadata:
  name: node-1
zones:
  - name: numa-0
    type: NUMA
    resources:
      nvidia.com/gpu: "4"
  - name: numa-1
    type: NUMA
    resources:
      nvidia.com/gpu: "4"
```

- `Filter`：检查 Pod 请求的 GPU 是否能在某个 zone 内满足。
- `Score`：优先选择拓扑紧凑的节点。

### CapacityScheduling（弹性配额）

引入 `ElasticQuota` CR，允许队列在空闲时借用其他队列的配额。

## 5.4 Volcano

Volcano 是一个面向 AI/HPC 批处理场景的独立调度器，提供 Job 级抽象。

### 核心对象

| 对象 | 作用 |
|---|---|
| `Job` | 描述一组任务及其依赖（DAG） |
| `PodGroup` | 同一 Job 的 Pod 集合，声明 minMember |
| `Queue` | 多租户队列，带权重与容量 |
| `Scheduler` | volcano-scheduler，独立替换 kube-scheduler |

### 调度流程

```text
用户提交 VolcanoJob
   │
   ▼
vc-job controller 创建 PodGroup + Pods
   │
   ▼
volcano-scheduler 维护 Session
   │
   ▼
按 Queue 权重选择队列 → 按 Job/Pod 优先级选择 Pod
   │
   ▼
Predicate（过滤） → NodeOrder（打分） → Gang 检查
   │
   ▼
统一 Allocate / Bind
```

### 与原生 K8s 的对比

| 维度 | kube-scheduler + Coscheduling | Volcano |
|---|---|---|
| 调度器 | 原生 | 独立 |
| 作业抽象 | Pod + PodGroup | Job + PodGroup + Queue |
| Gang | 插件实现 | 原生 |
| 队列公平 | 弱 | 强 |
| MPI/TF/PyTorch | 需自己封装 | 内置集成 |
| 适用场景 | 混合负载 | 纯训练/批处理 |

### 1.15-1.16 新特性（2026）

- **命名空间级 Queue（v1.16）**：租户可在自己 namespace 内建队列层级并使用管理员审批的资源池，配合 **fairshare 插件**（借鉴 Slurm 的使用量衰减算法）实现跨租户长期公平。
- **HyperNode**：把机柜/轨道级拓扑抽象为 HyperNode 树，支持 PodGroup 拓扑反亲和（把作业实例打散到不同拓扑域）；v1.16 起 HyperNode 控制器可独立部署，供其他调度器复用拓扑发现。
- **DRA 打分（v1.16）**：调度循环可感知 DRA 设备容量；v1.15.2 曾修复 DRA 容量记账安全漏洞（GHSA-j38h-7pfq-cxmw），1.15.0/1.15.1 用户应尽快升级。

## 5.5 Kueue

Kueue 是 Kubernetes SIG-scheduling 子项目，专注于“队列、配额、公平共享”。

### 核心对象

| 对象 | 作用 |
|---|---|
| `ClusterQueue` | 集群级资源池，声明总配额与权重 |
| `LocalQueue` | 命名空间级队列，指向某个 ClusterQueue |
| `Workload` | Kueue 对 Job/Deployment/StatefulSet 的抽象 |
| `ResourceFlavor` | 定义不同硬件 flavor（如 A100、H100、spot） |

### 工作流程

```mermaid
flowchart LR
    User[用户创建 Job] --> K[Kueue controller]
    K -- 创建 Workload
       标记 suspend --> API[kube-apiserver]
    API -- watch --> K
    K -- 检查 ClusterQueue 配额
       admit Workload --> API
    API -- 创建 Pod --> S[kube-scheduler]
    S -- bind --> API
```

### 多租户配额示例

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: cq-train
spec:
  namespaceSelector: {}
  resourceGroups:
    - coveredResources: ["nvidia.com/gpu"]
      flavors:
        - name: a100
          resources:
            - name: "nvidia.com/gpu"
              nominalQuota: "32"
              borrowingLimit: "8"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  name: team-a-train
  namespace: team-a
spec:
  clusterQueue: cq-train
```

### v0.19-v0.20 新特性（2026）

- **API 大版本切换（v0.20.0，2026-09）**：Kueue 停止服务 `kueue.x-k8s.io/v1beta1`，只保留 **v1beta2**——升级前必须用官方迁移脚本转换存量对象（当前稳定线 v0.20.2，2026-10-15）。
- **TAS（Topology Aware Scheduling）增强**：Topology 的 `levels`、ResourceFlavor 的 `nodeLabels/tolerations` 变为可变；TAS 把“Pod 应落在哪个拓扑域（机架/NUMA）”纳入准入决策，与 scheduler-plugins NRT 互补。
- **DRA 集成（alpha）**：`KueueDRADeviceFeasibility` 门允许在准入前按节点检查 DRA 设备可用性；支持 `DeviceTaintRule`；`adminAccess` 请求不计配额。
- **生态**：内置 KueueViz（带 RBAC 的队列可视化）、Trainer（Kubeflow Training Operator v2）集成、`LWSImmutableGroupSize`（Beta，默认开，封死 LeaderWorkerSet 配额绕过）。

## 5.6 拓扑发现与可观测模块

### GPU Feature Discovery（GFD）

GFD 读取 `nvidia-smi` 输出，为节点打上标签：

```text
nvidia.com/gpu.product=A100-SXM4-80GB
nvidia.com/gpu.memory=81920
nvidia.com/gpu.count=8
nvidia.com/mig.capable=true
nvidia.com/gpu.machine=DGX-A100
```

用户可以用 `nodeSelector` / `nodeAffinity` 把特定负载绑定到特定 GPU 型号。

### Node Feature Discovery（NFD）

NFD 给节点打通用硬件标签，GPU 相关标签如：

```text
feature.node.kubernetes.io/pci-10de.present=true
feature.node.kubernetes.io/cpu-cpuid.AVX512F=true
```

### DCGM-Exporter

把 DCGM 指标暴露为 Prometheus 格式：

| 指标 | 含义 |
|---|---|
| `DCGM_FI_DEV_GPU_UTIL` | GPU 利用率 |
| `DCGM_FI_DEV_FB_USED` | 显存已用 |
| `DCGM_FI_DEV_FB_FREE` | 显存空闲 |
| `DCGM_FI_DEV_XID_ERRORS` | Xid 错误码 |
| `DCGM_FI_DEV_TEMP` | GPU 温度 |
| `DCGM_FI_DEV_POWER_USAGE` | 功耗 |

这些指标不仅可以监控，也可以被自定义调度器或 autoscaler 消费。

## 5.7 DRA 驱动与 GPU Operator 26.x 的 DRA 编排

### NVIDIA DRA Driver（kubernetes-sigs/dra-driver-nvidia-gpu）

NVIDIA 在 KubeCon EU 2026 把 DRA driver 捐入 kubernetes-sigs（Apache-2.0），当前 v0.5.x（2026-08）。它由两部分组成：

| 组件 | 状态 | 作用 |
|---|---|---|
| ComputeDomain driver | **官方支持** | 把多机 NVLink 域（GB200 NVL72 整柜）声明为可分配资源，DRA 可按“整柜 72 GPU”做组合分配 |
| GPU kubelet plugin | **alpha，默认关闭** | 整卡 / MIG 细粒度分配与共享，Helm 需 `gpuResourcesEnabledOverride=true` 显式开启 |

生产建议：在 GPU kubelet plugin 达到 GA 质量之前，细粒度 GPU 分配继续使用 Device Plugin（或 KAI/HAMi 方案），DRA 先用于 ComputeDomain 与带属性的整卡选择（配合 1.37 扩展资源映射可无感接管 `nvidia.com/gpu`）。

### GPU Operator 26.x：GPUCluster CR

GPU Operator 从 26.7 起把 DRA 纳入 ClusterPolicy 之外的独立编排对象 `GPUCluster`：

```yaml
apiVersion: nvidia.com/v1
kind: GPUCluster
metadata:
  name: gpu-cluster
spec: {}   # 管理 DRA driver、ComputeDomain、DCGM、验证任务的生命周期
```

版本要点：

- **25.10.x（2025 末）**：全面支持 Blackwell——HGX B300、HGX GB300 NVL72、GB200 NVL72（含 OpenShift）、RTX Pro 6000；新增 B300（`1g.34gb`～`7g.269gb`）与 GB300 NVL72（`1g.35gb`～`7g.278gb`）MIG profile 及 `all-balanced`  profile；CDI 默认启用；支持 MIG-backed vGPU（KubeVirt/OpenShift）。
- **26.3.0**：动态 MIG 配置生成、Node Resource Interface（NRI）插件、GB200 NVL4 / RTX Pro 4500 支持。
- **26.7.0**：DRA 支持（GPUCluster）、ComputeDomain 多机 NVLink、KubeVirt GPU passthrough via DRA、驱动原地重启（in-place restart）；要求 K8s ≥ 1.34.2、驱动 ≥ 580、CDI 兼容运行时。

## 5.8 KAI Scheduler 与 llm-d：推理调度新模块

### KAI Scheduler

NVIDIA 2025-04 开源（源自 Run:ai 调度引擎，基于 kube-batch），2025-12 进入 CNCF Sandbox。它把 Gang、队列、fraction、TAS 整合进一个独立调度器：

| 能力 | 实现 |
|---|---|
| Gang / 层级 PodGroup | 原生支持；层级 PodGroup 可表达 PD 分离（prefill/decode 各为一组）等复合负载 |
| Fractional GPU | 基于 HAMi-core 拦截层的显存/算力配额，进程超额申请显存会被拒绝（硬隔离级） |
| 层级队列 | 配额、权重、优先级、公平策略（DRF + time-based fairshare + reclamation） |
| TAS | 拓扑感知与层级 TAS，覆盖 NVLink 域/机架维度 |
| 弹性与抢占 | elastic workloads、独立可配的可抢占性、min-guaranteed-runtime |
| DRA | 支持 NVIDIA DRA 路径，覆盖 GB200/GB300 |
| 可解释性 | 调度决策通过 Kubernetes Events 暴露，方便排查“为什么这个 Pod 没调上” |

与 Kueue 的组合定位：Kueue 强在“准入 + 公平共享”的控制平面语义与原生生态集成；KAI 强在“GPU 专属调度一步到位 + fraction 硬隔离”。已有 Run:ai 商业版或 NVIDIA AI Enterprise 的团队，KAI 是自然的开源落点。

### llm-d：推理感知的调度与路由

llm-d（CNCF，KubeCon EU 2026 由 IBM Research / Red Hat / Google Cloud 捐赠，NVIDIA / CoreWeave / AMD / Intel 等参与）不是调度器，而是跑在调度结果之上的**推理流量层**：

```text
请求 → Gateway（Gateway API）→ llm-d Router（KV Cache 亲和路由）
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
        prefill PodGroup            decode PodGroup          模型缓存侧车
        （计算密集，优先整柜 NVLink）  （显存/KV Cache 密集，    （前缀缓存同步）
                                     可按 fraction 超卖）
```

- **PD 分离**：prefill 与 decode 拆成独立 PodGroup，各自伸缩；调度器（KAI/Kueue/Volcano）保证每组 Gang 就位。
- **KV Cache 感知路由**：把请求路由到持有对应前缀缓存的 decode Pod，显著降低 TTFT。
- **生态集成**：与 vLLM、NVIDIA Dynamo/Grove（多节点推理编排）协同，是 2026 年推理调度的新范式参考实现。

## 5.9 多租户治理拼图

生产 GPU 集群通常把以下 K8s 原生对象与调度器组合使用：

| 对象 | 解决的问题 |
|---|---|
| `ResourceQuota` | 命名空间级 GPU 上限 |
| `LimitRange` | 默认/最大 GPU 请求 |
| `PriorityClass` | 训练/推理/调试优先级 |
| `PodGroup` | Gang all-or-nothing |
| `Queue` / `ClusterQueue` | 队列、公平共享、抢占 |
| `NetworkPolicy` | 多租户网络隔离 |
| `PodSecurity` | 容器安全基线 |

## 5.10 模块选型参考

| 需求 | 推荐组合 |
|---|---|
| 只想让 GPU 可被调度 | GPU Operator + Device Plugin |
| 需要 Gang 调度，不想换调度器 | GPU Operator + scheduler-plugins Coscheduling |
| 需要 Gang + 拓扑 + 弹性配额 | GPU Operator + scheduler-plugins Coscheduling + NRT + CapacityScheduling |
| 纯训练/批处理集群 | GPU Operator + Volcano |
| 多租户 AI 平台（原生生态） | GPU Operator + Kueue（v1beta2 API）+ TAS / NRT |
| GPU 一体集群（Gang + fraction + TAS） | GPU Operator + KAI Scheduler |
| 多机 NVLink（GB200 NVL72）整柜分配 | GPU Operator ≥ 26.7 + DRA（GPUCluster + ComputeDomain） |
| PD 分离推理平台 | 上述任一调度器 + llm-d（KV Cache 感知路由） |
| 需要显存感知调度 | KAI fraction（HAMi-core）/ HAMi / 自定义调度器 |

## 5.11 本章小结

| 模块 | 核心职责 | 源码入口（下一章展开） |
|---|---|---|
| NVIDIA Device Plugin | 把 GPU 暴露为 `nvidia.com/gpu` | `NVIDIA/k8s-device-plugin` |
| NVIDIA DRA Driver | 声明式设备分配（属性/污点/ComputeDomain） | `kubernetes-sigs/dra-driver-nvidia-gpu` |
| NVIDIA GPU Operator | 自动化节点 GPU 组件生命周期（含 26.7 起 DRA 编排） | `NVIDIA/gpu-operator` |
| scheduler-plugins | 在原生调度器内扩展 Gang/拓扑/弹性配额 | `kubernetes-sigs/scheduler-plugins` |
| Volcano | 独立批处理调度器（v1.16：命名空间队列、fairshare） | `volcano-sh/volcano` |
| Kueue | 队列与公平共享准入（v0.20：v1beta2 API、TAS、DRA alpha） | `kubernetes-sigs/kueue` |
| KAI Scheduler | GPU 一体化调度（Gang/fraction/TAS/DRA） | `NVIDIA/KAI-Scheduler` |
| llm-d | 推理 PD 分离 + KV Cache 感知路由 | `llm-d/llm-d` |
| GFD / NFD / DCGM | 拓扑发现、标签、可观测 | 对应 DaemonSet 与 exporter |

下一章我们进入源码，看这些模块的调用链是如何串起来的。
