# 2. 核心思想

> 一句话理解：Kubernetes 的全部设计都围绕一个原点——**"声明期望状态，让控制循环把它收敛为现实"**。理解了这一句，Pod、Controller、Operator、调度框架、CRD 全是它的推论。

## 2.1 声明式 API（Declarative API）

这是 K8s 与传统运维脚本最本质的区别：

| 风格 | 你说什么 | 系统做什么 |
|---|---|---|
| **命令式（Imperative）** | "启动一个 nginx 容器" / "杀掉它" / "重启它" | 严格执行命令，不关心结果是否持续 |
| **声明式（Declarative）** | "我想要 3 个 nginx 副本一直在运行" | 持续观测，发现只有 2 个就再起 1 个，发现 4 个就杀 1 个 |

在 K8s 里你写的是 `Deployment`：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
spec:
  replicas: 3
  selector:
    matchLabels: { app: vllm }
  template:
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          resources:
            limits: { nvidia.com/gpu: 1 }
```

你**没有**说"在哪台机器上跑""什么时候启动""崩了怎么办"——你只声明了**期望状态（desired state）**：3 个带 GPU 的副本。剩下的交给 K8s。

声明式的好处：

- **幂等**：同一个 YAML `apply` 一百次，结果一样。
- **可diff/可审计**：`kubectl diff`、GitOps（把 YAML 放 Git）让基础设施变更像代码评审一样可追踪。
- **自愈**：期望状态存在 etcd 里，任何偏离都会被控制器纠正——这比"写个 cron 检查并重启"健壮得多。

## 2.2 控制循环（Reconcile Loop）

把声明式变成现实的核心机制是**控制循环**：每个控制器都是一个**永不退出的循环**，反复执行：

```text
       观测实际状态          计算差异           执行动作
observed  ──────────►  diff  ──────────►  act  ──┐
   ▲                                            │
   └──────────────  再次观测  ◄─────────────────┘
                       (永远)
```

伪代码：

```python
while True:
    desired = read_from_etcd("期望副本数")      # spec.replicas
    observed = list_pods(matching_selector)     # 实际运行的 Pod
    diff = desired - len(observed)
    if diff > 0:
        create_pods(diff)
    elif diff < 0:
        delete_pods(-diff)
    sleep(short_interval)
```

这叫 **reconcile（调和/收敛）**。关键洞察：

- 控制器**不保存"上一步做了什么"**这种易错的中间状态，它每次都从当前真实状态出发重新计算。即使错过某个事件、重启、网络抖动，下一轮循环仍会收敛到正确状态。
- 这是**最终一致性（eventual consistency）**而非强一致——系统保证"最终会到达期望状态"，但不保证"立即"。
- K8s 里几乎所有自动化都是控制循环：Deployment 控制器、ReplicaSet 控制器、Node 控制器、Endpoint 控制器、Job 控制器……以及你写的每一个 Operator。

> **重要区分**：控制循环 ≠ 事件驱动。K8s 既用**事件**（etcd watch / informer）来"尽快"触发 reconcile，也靠**定时 resync**（list 全量）来兜底——即使丢了事件，resync 也会纠正漂移。这种"事件加速 + 周期兜底"的设计是 K8s 鲁棒性的来源。

## 2.3 期望状态 vs 观测状态（Desired vs Observed）

这是贯穿 K8s 心智模型的对偶：

| | 期望状态（Spec） | 观测状态（Status） |
|---|---|---|
| 来源 | 用户写在 YAML 的 `spec` | 系统回填到 `status` |
| 谁写 | `kubectl apply` / Controller | Controller / kubelet / scheduler |
| 例子 | `replicas: 3` | `readyReplicas: 2`（还有 1 个没就绪） |
| 存哪 | etcd | etcd |

控制循环的任务就是让 `status` 逼近 `spec`。任何 K8s 资源（包括你用 CRD 自定义的）都遵循 `spec` + `status` 两段式结构。

## 2.4 Pod：最小的调度单元

**Pod** 是 K8s 调度的最小单元，不是容器。一个 Pod 里可以有一个或多个容器，它们：

- **共享网络命名空间**：同一 Pod 内容器用 `localhost` 互通，端口不冲突。
- **共享存储卷**：可以挂载同一个 emptyDir / PVC。
- **共享 IPC/UTS 命名空间**。
- **被一起调度、一起生死**：同一 Pod 的容器总在同一节点，总一起创建/销毁。

为什么是 Pod 而不是容器？经典场景是 **sidecar（边车）**：主容器跑业务（如 vLLM 推理），sidecar 跑日志采集 / service mesh proxy / 模型权重预拉取。它们需要紧耦合（同网络、同生命周期），Pod 把这种耦合表达为一等公民。

> **Sidecar 容器（v1.33 GA）**：早期 sidecar 与普通容器没有区别，主容器退出会导致 sidecar 一起死（反之亦然）。K8s 引入了 `initContainers` 中的 `restartPolicy: Always` 标记的**原生 sidecar**（KEP-753），它会在主容器启动前先就绪、在主容器退出后优雅结束，解决了 Job 类工作流里 sidecar 拖死 Job 的经典痛点。

Pod 的资源声明决定了它能否被调度：

```yaml
resources:
  requests: { cpu: "2", memory: "8Gi", nvidia.com/gpu: 1 }  # 调度依据（保证）
  limits:   { cpu: "4", memory: "16Gi", nvidia.com/gpu: 1 }  # 上限（cgroup 限制）
```

- `requests` 是**调度依据**：kube-scheduler 据此判断节点能不能放下。
- `limits` 是**运行时上限**：kubelet/CRI 据此设置 cgroup 限制。
- **CPU 是可压缩资源**（throttle，不杀进程），**内存是不可压缩资源**（超 limit 会被 OOMKill），**GPU 是整数独占资源**（默认不可分片，除非用 MIG/MPS）。

## 2.5 Controller 模式

**Controller** = "观察某类资源的期望状态，并驱动实际行动去实现它"的控制循环。K8s 内置大量控制器，都在 `kube-controller-manager` 里运行：

| 控制器 | 观察的资源 | 实现的行动 |
|---|---|---|
| **ReplicaSet** | RS 的 `replicas` | 增删 Pod 使副本数匹配 |
| **Deployment** | Deployment | 滚动管理多个 ReplicaSet（新版/旧版），实现滚动发布与回滚 |
| **StatefulSet** | StatefulSet | 为每个 Pod 分配稳定网络标识（`pod-0`/`pod-1`）与持久卷，适合数据库 |
| **DaemonSet** | DaemonSet | 保证每个（或符合条件的）节点跑一个副本，适合日志/监控/GPU daemon |
| **Job / CronJob** | Job | 保证 N 个 Pod 成功完成，失败重试 |
| **Node** | Node | 节点失联后驱逐其上的 Pod（重新调度） |
| **Endpoint / EndpointSlice** | Service + Pod | 维护 Service 背后的健康 Pod IP 列表 |
| **ServiceAccount / Token** | ServiceAccount | 自动挂载投影 token |

控制器的代码结构高度一致，都遵循 **watch → inform → reconcile**：

```text
etcd  ──watch──►  Informer(本地缓存+事件队列)  ──►  workqueue  ──►  reconcile(key)
                          ▲                                          │
                          └────── resync(定期全量 list) ──────────────┘
```

`client-go` 的 `Informer` 机制让控制器不必每次都请求 apiserver，而是维护一份本地缓存 + 接收增量事件，极大降低 apiserver 压力。详见 [第 6 章源码分析](06-source-analysis)。

## 2.6 Operator 模式

**Operator = Controller + 领域知识**。当你想自动化管理某个复杂有状态应用（如数据库、分布式训练、消息队列），内置控制器不够用，就写一个 Operator：

1. 用 **CRD（Custom Resource Definition）** 定义一类新资源，如 `MPIJob`、`RayCluster`、`Kafka`。
2. 写一个控制器（叫 **Operator**），它的 reconcile 逻辑编码了"如何把一个 `MPIJob` 变成一组真正在跑的 Pod + Service + ConfigMap + …"。

```yaml
# 一个 RayCluster CRD 实例——声明式地描述一个 Ray 集群
apiVersion: ray.io/v1
kind: RayCluster
metadata: { name: my-ray }
spec:
  headGroupSpec: { ... }
  workerGroupSpecs: [ { replicas: 3, ... } ]
```

KubeRay Operator 看到 `RayCluster` 资源，就按 spec 创建 head Pod、worker Pod、Service、自动伸缩——你不需要手动 `kubectl create pod`。

> Operator 的本质：**把运维 SRE 的领域知识（"启动一个分布式训练需要哪些步骤""节点挂了怎么恢复"）编码成代码**，让 K8s 像管理 Deployment 一样管理它。这正是为什么 GPU Operator、Training Operator、KServe、KubeRay、Volcano 都用 Operator 模式——它们把"在 K8s 上跑 AI"这件事的复杂度封装成了声明式资源。

Operator 与普通 Controller 的边界其实模糊；社区共识是：**管理有状态/复杂应用的、带 CRD 的控制器**叫 Operator。

## 2.7 标签与选择器（Labels & Selectors）

K8s 用**松耦合**而非强引用来关联资源。Service 怎么知道要把流量发给哪些 Pod？不是存 Pod 的 UID，而是用标签选择器：

```yaml
# Service
spec:
  selector: { app: vllm }      # 选所有带 app=vllm 标签的 Pod
---
# Pod
metadata:
  labels: { app: vllm }        # 被 Service 选中
```

这种设计让资源之间**解耦**：删 Pod、加 Pod，Service 自动跟上，无需修改引用。标签是 K8s 里最重要的"软连接"。`kubectl label`、调度亲和性、NetworkPolicy 都基于它。

## 2.8 三大扩展接口：CRI / CNI / CSI

K8s 把"运行容器""配置网络""挂载存储"三件事抽象成接口，让具体实现可插拔：

| 接口 | 全称 | 解决什么 | 典型实现 |
|---|---|---|---|
| **CRI** | Container Runtime Interface | kubelet 如何启动/停止容器 | containerd、CRI-O（Docker via dockershim 已于 v1.24 移除） |
| **CNI** | Container Network Interface | Pod 如何获得网络（IP、连通性） | Calico、Cilium（eBPF）、Flannel、AWS VPC CNI |
| **CSI** | Container Storage Interface | Pod 如何挂载持久卷 | 各云厂商（EBS/EFS/PD）、本地存储、NFS、Longhorn |

**关键事实**：一个 K8s 集群**必须安装一个 CNI 网络插件**才能拥有可工作的 Pod 网络。官方文档明确："Your Kubernetes cluster needs a network plugin in order to have a working Pod network"。缺少 CNI 时，Pod 会卡在 `ContainerCreating`、CoreDNS 停在 `Pending`、Pod 间无法通信——这是新手最常见的"集群装好了但啥都用不了"问题。

> CRI 自 **v1.26** 起成为 kubelet 的硬性要求（`dockershim` 在 v1.24 移除，v1.26 完成清理）。这意味着运行时必须实现 CRI 的 gRPC 接口，kubelet 作为 gRPC 客户端调用它来管理容器生命周期。

## 2.9 调度框架（Scheduling Framework）

kube-scheduler 不再是"写死的算法"，而是一个**插件化的调度流水线**。它把"为一个 Pod 选节点"的过程切分成 **12 个扩展点**（extension points），每个扩展点可以挂插件：

```text
PreEnqueue → QueueSort → [PreFilter → Filter → PostFilter → PreScore → Score]
          → [Reserve → Permit → PreBind → Bind → PostBind]
                     └─── 调度周期(串行) ───┘ └─── 绑定周期(可并发) ───┘
```

- **调度周期（Scheduling Cycle）**：为 Pod 选定一个节点，**串行执行**（一次只调度一个 Pod，保证决策一致）。
- **绑定周期（Binding Cycle）**：把决策真正写到 etcd（更新 Pod 的 `nodeName`），**可并发**（多个 Pod 可同时绑定）。

`Filter`（过滤掉不满足条件的节点，如资源不够）、`Score`（给剩余节点打分，如 binpack/spread）、`PostFilter`（都没节点时尝试抢占）是最常被替换/扩展的扩展点。**自 v1.19 起 GA**。

> 这是 K8s 能支撑 AI 负载的关键：Gang Scheduling、拓扑感知（NUMA/GPU 分组）、负载感知都可以写成调度插件，挂到对应扩展点，而不必 fork kube-scheduler。详见 [第 5 章](05-core-modules) 与 [第 6 章源码](06-source-analysis)。

## 2.10 与相邻概念的边界

| 概念 | 它是什么 | 与 K8s 的边界 |
|---|---|---|
| **Docker / containerd** | 容器运行时 | K8s 通过 CRI 调用它；K8s 不"跑容器"，kubelet 调 CRI 跑容器 |
| **Helm** | K8s 的包管理器（模板化 YAML） | 部署时的"apt"，不参与运行时 |
| **Service Mesh（Istio/Linkerd）** | 流量治理 sidecar | 在 K8s 之上，通过 admission 注入 sidecar + CRD 配置 |
| **ArgoCD / Flux（GitOps）** | 把 Git 里的 YAML 同步到集群 | K8s 的"持续部署层"，不改变 K8s 本身 |
| **Ray** | 分布式 Python 计算 | K8s 管节点与部署（KubeRay），Ray 管集群内任务调度 |
| **Volcano** | K8s 上的批调度系统 | 一组调度插件 + CRD（PodGroup），让 K8s 支持 Gang/队列调度 |
| **Borg（Google 内部）** | K8s 的"前辈" | 思想同源（声明式、控制循环、Pod），但 Borg 规模/硬件协同设计远超开源 K8s |

## 本章小结

Kubernetes 的核心思想可以用一句话和三组对偶概括：

- **一句话**：声明期望状态，让控制循环把它收敛为现实。
- **对偶 1**：Spec（你想要的）↔ Status（系统观测到的）。
- **对偶 2**：声明式（what）↔ 命令式（how）。
- **对偶 3**：期望（desired）↔ 观测（observed），中间靠 reconcile 弥合。

Pod、Controller、Operator、调度框架、CRI/CNI/CSI、CRD 都是这一思想的派生：Pod 是调度的最小声明单元，Controller 是执行 reconcile 的代码，Operator 是带领域知识的 Controller，调度框架是可插拔的"选节点"流水线，CRI/CNI/CSI 把运行时/网络/存储解耦成接口，CRD 让你能声明任意新资源。把握住"声明式 + 控制循环"，后面所有的架构与源码都会变得顺理成章。

**参考来源**

- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/)
- [Kubernetes API Convention — Declarative](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- [Controller pattern / Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Compute, Storage, and Networking Extensions（CNI/CSI/Device Plugin）](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/)
- [Network Plugins（CNI 必需性）](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
- [Scheduling Framework](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/)
- [Sidecar Containers (KEP-753, GA in v1.33)](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
