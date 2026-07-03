# 5. 核心模块

> 一句话理解：把 [第 3 章](03-architecture) 的组件展开成模块级详解——每个模块"做什么、怎么做、关键参数与坑"，重点讲透对 AI 平台最关键的**调度框架**与**Device Plugin / GPU Operator**。

## 5.1 kube-apiserver

**职责**：集群唯一入口，处理所有读写请求。

**关键处理链**（请求 → 响应）：

```text
HTTP 请求 → 认证(AuthN) → 授权(AuthZ) → Mutating Admission → Validating Admission →
schema 校验 → etcd 读写 → (可选) admission mutation → 序列化响应
```

**对 AI 平台重要的能力**：

- **Watch API**：长连接，资源变更推流给客户端（scheduler/controller/kubelet 都靠它）。
- **etcd 是唯一后端**：apiserver 在内存里做"对象 ↔ etcd KV"的序列化/反序列化、缓存、watch 聚合。
- **聚合层（Aggregation）**：可挂自定义 API Server（如 metrics-server、metrics-aggregator）。
- **关键参数**：`--max-requests-inflight`（并发上限，大集群要调大）、`--default-watch-cache-size`。

**坑**：大集群（>1000 节点）时 apiserver 是瓶颈，watch 带宽/对象数要控制；用 `ResourceVersion` 做乐观并发控制（CAS）。

## 5.2 etcd

**职责**：强一致 KV 存储，集群唯一真相。

**模型**：

- 基于 **Raft 共识**：写需多数派（quorum）确认。
- K8s 把每个资源对象存为一个 KV：key 形如 `/registry/pods/default/my-pod`。
- 支持**范围查询与 watch**（前缀 watch 是 informer 的基础）。
- **Lease + TTL**：支持 leader election、kubelet 节点心跳。

**生产关键参数**：

| 参数 | 含义 | 建议 |
|---|---|---|
| `--quota-backend-bytes` | 存储上限 | 默认 2GB，到 8GB 告警 |
| 磁盘 | etcd 对 fsync 延迟极敏感 | 独立 SSD（最好是 NVMe），不要与其他 IO 混部 |
| 副本数 | Raft 多数派 | 3 或 5（不要偶数，浪费且不提升容错） |
| `--heartbeat-interval` / `--election-timeout` | Raft 心跳 | 跨区域部署需调大 |

**坑**：

- 单 key 上限 ~1.5MB——别往 ConfigMap/Annotation 塞大文件（用对象存储）。
- 大量 watch 同一前缀会打满 etcd——apiserver 做了 watch 缓存分担。
- 定期 `etcdctl defrag` 回收碎片（在线 defrag 要逐节点做，避免同时影响多数派）。

## 5.3 kube-scheduler 与调度框架

这是 K8s 对 AI 平台最重要的组件之一。**调度框架（Scheduling Framework）自 v1.19 GA**，把"为 Pod 选节点"切分成一条可插拔流水线。

### 两个周期

官方文档原文：

> Each attempt to schedule one Pod is split into two phases, the **scheduling cycle** and the **binding cycle**. Scheduling cycles are run **serially**, while binding cycles **may run concurrently**.

- **调度周期（Scheduling Cycle）**：选定节点，串行（一次一个 Pod，保证决策一致）。
- **绑定周期（Binding Cycle）**：把 `nodeName` 写回 apiserver，可并发。

### 12 个扩展点

```text
           ┌─────────────── 调度周期（串行）────────────────┐
PreEnqueue │ QueueSort(排序) → PreFilter → Filter → PostFilter
           │                          → PreScore → Score → Reserve → Permit
           └──────────────────────────────────────────────────┘
                                       │
           ┌─────────────── 绑定周期（并发）────────────────┐
           ▼
         PreBind → Bind → PostBind
           └──────────────────────────────────────────────────┘
```

| 扩展点 | 作用 | 典型插件 |
|---|---|---|
| `PreEnqueue` | Pod 入队前检查（如 PodGroup 未就绪则不入队） | Coscheduling |
| `QueueSort` | 给待调度 Pod 排序（决定谁先调度） | PrioritySort |
| `PreFilter` | 预处理/校验 Pod（算总资源、检查必选字段） | NodeResourcesFit |
| `Filter` | 过滤不合格节点（资源/亲和/污点/GPU） | NodeResourcesFit, NodeAffinity, TaintToleration, PodTopologySpread |
| `PostFilter` | Filter 后无节点 → 尝试抢占 | DefaultPreemption |
| `PreScore` | 打分前准备 | - |
| `Score` | 给幸存节点打分 | NodeResourcesBalancedAllocation, ImageLocality, PodTopologySpread |
| `Reserve` | 预占资源（绑定前先占住，防超额） | NodeResourcesFit |
| `Permit` | 允许"延迟绑定"或"等待"（Gang 调度核心） | Coscheduling |
| `PreBind` | 绑定前准备（如先挂卷） | VolumeBinding |
| `Bind` | 写 nodeName | DefaultBinder |
| `PostBind` | 绑定后回调 | Coscheduling |

### 内部数据结构：CycleState

调度框架在单次调度内用 `CycleState` 在插件间传状态。其底层是 Go 的 `sync.Map`——官方注释说明它优化"write once, read many times"模式，并保证并发安全。

### 默认调度策略（HYBRID）

K8s 默认调度是"先 pack 后 spread"的混合：

1. **Filter**：硬约束（资源够不够、亲和满不满足、污点容不容忍）。
2. **Score**：
   - `NodeResourcesBalancedAllocation`：倾向于把 Pod 放到"放进去后资源利用率最均衡"的节点（pack）。
   - `PodTopologySpread`：在拓扑域（zone/rack）间打散（spread）。
   - `InterPodAffinity`：亲/反亲和。

> 这与 [Ray 的 HYBRID 调度](/03-ai-platform/ray/02-core-ideas) 思想一致：先聚合作 locality，超阈值再打散。但 K8s 的粒度是 Pod，Ray 的粒度是 task。

### v1.36 原生 PodGroup / Gang 调度

**自 Kubernetes v1.36.0 起**，调度框架**原生支持 PodGroup 调度**——对照 v1.34/v1.35 源码，`PodGroupPostFilterPlugin`、`RunPlacementGeneratePlugins`、`RunPlacementScorePlugins` 等接口仅在 v1.36.0 出现。对应 KEP：

- **KEP-4671**：Gang Scheduling（all-or-nothing）。
- **KEP-5598**：Opportunistic Batching。

意义：Gang 调度（训练 Job 需要的所有 Pod 要么全调度成功要么全不调度，避免只起一半导致死锁/资源浪费）此前只能靠 out-of-tree 的 **Volcano** 或 **scheduler-plugins 的 Coscheduling**，现在走向 in-tree 原生支持。

### scheduler-plugins（out-of-tree 官方插件仓）

`kubernetes-sigs/scheduler-plugins` 是官方维护的、基于调度框架构建的 out-of-tree 插件仓库，**独立于核心 kube-scheduler 二进制**（部署为 secondary scheduler）。面向生产的插件包括：

| 插件 | 解决 | AI 场景 |
|---|---|---|
| **Capacity Scheduling** | 按队列/租户做弹性容量预留 | 多团队共享 GPU 集群 |
| **Coscheduling** | Gang 调度（基于 PodGroup CRD） | 分布式训练 all-or-nothing |
| **Node Resource Topology** | NUMA/PCIe 设备拓扑感知调度 | GPU 分组、NUMA 绑核 |
| **Trimaran**（TargetLoadPacking/LoadVariationRiskBalancing） | 负载感知调度 | 避免热点节点 |
| **Network-Aware Scheduling** | 网络拓扑/带宽感知 | RDMA/跨机通信密集型 |

## 5.4 kube-controller-manager

跑内置控制器的进程，每个都是独立 reconcile loop：

- **Node Controller**：watch 节点心跳，失联超时标记 `NotReady`，继续失联则驱逐 Pod（触发重调度）。
- **Deployment Controller**：管理多个 ReplicaSet 的比例（滚动）。
- **ReplicaSet Controller**：维持每个 RS 的副本数。
- **StatefulSet / DaemonSet / Job / CronJob Controller**：对应工作负载。
- **Endpoint(Slice) Controller**：维护 Service 的健康后端列表。
- **ServiceAccount / Token Controller**：默认账号与挂载 token。
- **garbage collector**：级联删除（删 Deployment → 删 RS → 删 Pod）。

## 5.5 kubelet

**职责**：节点代理，把分配到本节点的 Pod 真正跑起来并维持。

**核心机制**：

- **PLEG（Pod Lifecycle Event Generator）**：周期性（默认 1s）通过 CRI 查询本节点所有容器状态，对比缓存，产生 Pod 生命周期事件，触发 `syncPod`。
- **syncPod**：对一个 Pod 做一致性收敛——对比"期望容器列表"与"实际容器列表"，创建缺的、删除多的、重启需要的。
- **状态上报**：周期 PATCH `node.status`（容量、已用、Condition）和 `pod.status`。
- **探针执行**：liveness/readiness/startup。
- **cAdvisor**：内置容器资源指标采集。

**关键参数**：`--max-pods`（默认 110，AI 节点通常调小，因为单 Pod 资源大）、`--pod-max-pids`、驱逐阈值 `--eviction-hard`（磁盘/内存紧张时主动驱逐）。

## 5.6 kube-proxy

**职责**：维护 Service VIP → Pod IP 的转发规则。

**模式**：

- **iptables（默认）**：规则是全量重写，Pod 多时（数千 Service × 数万 Pod）更新慢、匹配链长。
- **IPVS**：基于内核哈希表，大规模下性能与更新速度远优于 iptables，**大集群必选**。
- **ebpf（Cilium 等可替换）**：绕过 iptables/kube-proxy，性能最优。

## 5.7 CRI（Container Runtime Interface）

**职责**：把"如何管理容器"抽象成 gRPC 接口，kubelet 是客户端。

**主要 gRPC 服务**：

- `RuntimeService`：`RunPodSandbox` / `StopPodSandbox` / `RemovePodSandbox` / `ListPodSandbox`；容器生命周期 `CreateContainer`/`StartContainer`/`StopContainer`/`RemoveContainer`；`ContainerStats`。
- `ImageService`：`ListImages`/`PullImage`/`RemoveImage`。

**实现**：containerd（最主流）、CRI-O。Docker 曾通过 `dockershim` 适配，已于 **v1.24 移除，v1.26 起 kubelet 硬性要求运行时实现 CRI**。

## 5.8 CNI（Container Network Interface）

**职责**：为 Pod 分配 IP、配置网络命名空间、打通 Pod 间通信。

**关键事实**：集群**必须**装一个 CNI 插件，否则 Pod 卡 `ContainerCreating`、CoreDNS 卡 `Pending`。

**主流实现**：

| CNI | 特点 | 适合 |
|---|---|---|
| **Calico** | BGP 路由，成熟稳定，支持 NetworkPolicy | 通用 |
| **Cilium** | 基于 eBPF，高性能，可替换 kube-proxy，支持 L7 策略 | 大规模、性能敏感 |
| **Flannel** | 简单 overlay（VXLAN），功能少 | 学习/小集群 |
| **AWS VPC CNI** | 直接用 AWS VPC IP，无 overlay | EKS |
| **Multus** | **多网卡**（一个 Pod 多个 CNI 接口） | **AI 训练：一张卡存储、一张卡 RDMA** |

> AI 训练常需要 Pod 同时有"存储网络"和"RDMA 计算网络"两张卡——**Multus + SR-IOV / IPoIB** 是标准方案。

## 5.9 CSI（Container Storage Interface）

**职责**：把"如何挂载存储卷"抽象成接口，让存储厂商可插拔。

**模型**：

- `Provisioner`：创建卷（`PersistentVolume`）。
- `Attacher`：把卷 attach 到节点。
- `Mounter`：把卷 mount 到容器路径。
- `Snapshotter`：卷快照。

**流程**：用户声明 `PersistentVolumeClaim` → `StorageClass` 的 provisioner 动态创建 `PV` → attach + mount 到 Pod。

**AI 场景选型**：

- **本地盘（Local PV / 直接挂 NVMe）**：训练 checkpoint、模型权重、数据集——延迟最低，但 Pod 绑定节点，需配合调度。
- **并行文件系统（Lustre / GPFS / WekaFS / JuiceFS）**：多 Pod 共享大数据集。
- **对象存储（S3/OSS）+ CSI/Fuse**：海量小文件、便宜。
- **网络块存储（EBS/PD）**：单 Pod 持久化，延迟中等。

## 5.10 DNS（CoreDNS）

**职责**：集群内服务发现 DNS。

- Pod 里 `/etc/resolv.conf` 指向 CoreDNS。
- `my-svc.my-ns.svc.cluster.local` → Service ClusterIP。
- Headless Service（`clusterIP: None`）→ 直接返回 Pod IP 列表（StatefulSet 常用：`pod-0.my-svc` 解析到具体 Pod）。

## 5.11 Ingress 与 Gateway API

**职责**：把集群外部的 HTTP/HTTPS 流量路由到集群内 Service。

- **Ingress**（传统）：通过 Ingress Controller（nginx-ingress、Traefik）实现 7 层路由，配合证书做 TLS 终结。能力有限（主要是路径/host 路由）。
- **Gateway API**（新一代，由 SIG-Network 推动）：更 expressive 的 CRD 模型（`GatewayClass`/`Gateway`/`HTTPRoute`/`GRPCRoute`），支持多租户、跨命名空间、TCP/UDP/gRPC。**Gateway API 的 HTTPRoute 已 GA**，正在成为 K8s 流量入口的事实标准。

> LLM Gateway、推理服务的对外暴露，推荐用 Gateway API（或 Service Mesh）而非裸 Ingress——它对多版本路由（金丝雀/影子流量）和 gRPC 流式（vLLM 的流式输出）支持更好。

## 5.12 自动扩缩：HPA / VPA / CA

| 组件 | 扩什么 | 依据 |
|---|---|---|
| **HPA（HorizontalPodAutoscaler）** | Pod **副本数** | CPU/内存或**自定义指标**（如 QPS、队列长度、GPU 利用率） |
| **VPA（VerticalPodAutoscaler）** | 单 Pod **资源 request/limit** | 历史用量 |
| **CA（Cluster Autoscaler）** | **节点数** | 有 Pod 因资源不足 Pending → 触发云 API 加节点 |
| **Karpenter**（AWS/社区） | **节点数**（更灵活） | 按 Pod 需求直接选合适机型，比 CA 快 |

> 推理服务弹性：HPA 按自定义指标（如 `vllm:num_requests_running` 或 Prometheus 的 tokens/s）扩缩，配合 CA/Karpenter 扩节点。注意 GPU Pod 启动慢（拉镜像+加载模型），HPA 要预留预热时间或用预测性扩缩。

## 5.13 RBAC 与准入控制

**RBAC（Role-Based Access Control）**：`Role`/`ClusterRole`（权限）+ `RoleBinding`/`ClusterBinding`（绑定到用户/组/ServiceAccount）。

**Admission Webhook**：准入链里的可插拔校验/改写，是平台治理的利器：

- **Mutating**：注入 sidecar（Istio）、注入默认 `resources.requests`、注入 node selector。
- **Validating**：强制镜像来自白名单 registry、强制必须设 `resources.limits`、禁止特权容器、合规检查（如 GPU Pod 必须带优先级）。

> 生产 AI 平台几乎必装准入策略：强制 GPU Pod 设优先级与抢占策略、强制镜像签名验证、强制 namespace 配额。可用 **Kyverno** 或 **OPA Gatekeeper** 声明式管理。

## 5.14 Metrics Server 与可观测

- **Metrics Server**：聚合器，提供 `kubectl top` 的 CPU/内存指标，是 HPA 的默认数据源。
- **kube-state-metrics**：暴露 K8s 对象状态（副本数、Pod phase、Deployment 状态）给 Prometheus。
- **Prometheus + Grafana**：事实标准的监控栈。
- **cAdvisor**（kubelet 内置）：容器级资源指标。

> AI 负载的可观测需补充 GPU 指标：**DCGM-Exporter**（NVIDIA）暴露 GPU 利用率/显存/温度/功耗，详见 [AI SRE 主题](/07-ai-sre/)。

## 本章小结

K8s 的核心模块可以按"决策—执行—治理—扩展"四类记忆：**决策**（apiserver/etcd/scheduler/controller-manager）、**执行**（kubelet/kube-proxy/CRI/CNI/CSI/DevicePlugin）、**治理**（RBAC/Admission/ResourceQuota/HPA-VPA）、**扩展**（CRD/调度框架/Gateway API）。对 AI 平台最关键的是**调度框架**（可插拔选节点，支撑 Gang/拓扑/负载感知）与 **Device Plugin + GPU Operator**（把 GPU 变成一等可调度资源）。v1.36 原生 PodGroup 调度是 Gang 调度走向 in-tree 的里程碑。

**参考来源**

- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/)
- [Scheduling Framework（GA v1.19，12 扩展点，调度/绑定周期）](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/)
- [pkg/scheduler/framework 源码](https://pkg.go.dev/k8s.io/kubernetes/pkg/scheduler/framework)
- [KEP-624 Scheduling Framework](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/624-scheduling-framework/kep.yaml)
- [scheduler-plugins 官方仓库](https://scheduler-plugins.sigs.k8s.io/)
- [Compute, Storage, and Networking Extensions](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/)
- [Network Plugins（CNI 必需性）](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
- [Device Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
