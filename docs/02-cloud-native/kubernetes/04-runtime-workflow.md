# 4. Runtime 工作流程

> 一句话理解：把"声明"变成"运行"的过程是一条**事件驱动的流水线**——apiserver 写入期望状态，scheduler、controller、kubelet 各自 watch 自己关心的部分，通过控制循环把状态一步步往前推进，直到 Pod 真正在节点上跑起来并持续上报。

本章把 [第 3 章](03-architecture) 的静态架构展开成**动态时序**，分四条主线讲清楚运行时如何工作。

## 4.1 主线一：从 `kubectl apply` 到 Pod Running

这是最常被问到的一条链路（也是面试高频题）。完整时序：

```text
1. kubectl apply -f pod.yaml
   └─ 读 kubeconfig，HTTPS POST JSON 到 apiserver

2. apiserver 处理请求
   ├─ Authentication：识别调用者身份（证书/token/OIDC）
   ├─ Authorization：RBAC 检查能否 create pods
   ├─ Admission（Mutating）：可改对象——如注入 sidecar、补默认值、强制 imagePullPolicy
   ├─ Admission（Validating）：只校验——如必须设 resources.requests、镜像必须来自白名单 registry
   ├─ Schema / 字段校验（OpenAPI）
   └─ 写入 etcd（Pod nodeName="", phase=Pending, conditions=[]）

3. scheduler watch 到新 Pod（spec.nodeName 为空）
   ├─ PreEnqueue / QueueSort：入调度队列
   ├─ 调度周期（串行）：
   │    ├─ PreFilter：预处理（如算 Pod 需要多少资源）
   │    ├─ Filter：逐节点过滤（资源够？亲和满足？污点容忍？GPU 够？）
   │    ├─ PostFilter：Filter 后无可用节点 → 尝试抢占（驱逐低优先级 Pod 腾位）
   │    └─ Score：对幸存节点打分（binpack/spread/负载/亲和分）
   ├─ Reserve：预占资源
   └─ 绑定周期（可并发）：Bind 把 nodeName 写回 apiserver

4. 目标节点 kubelet watch 到 nodeName==self 的 Pod
   ├─ Admission（kubelet 侧）：校验本节点资源、镜像、卷
   ├─ Device Plugin Allocate：分配 GPU（设 NVIDIA_VISIBLE_DEVICES、挂载 /dev/nvidia*）
   ├─ CRI RunPodSandbox：
   │    └─ CNI 插件为 Pod 创建网络命名空间、分配 Pod IP、配置路由
   ├─ CSI：把 PVC 对应的卷 attach 到节点 + mount 到容器路径
   ├─ CRI CreateContainer（按 Pod 里每个 container）
   ├─ CRI StartContainer
   └─ 启动探针：startup → readiness → liveness

5. kubelet 持续上报
   └─ 周期 PATCH pod.status（phase、podIP、containerStatuses、conditions）
```

每一步的失败都对应可观测的症状：

| 症状 | 卡在哪 | 排查 |
|---|---|---|
| 一直 `Pending` | scheduler 没选到节点 | `kubectl describe pod` → Events；通常是资源不足/亲和不满足/污点不容忍 |
| 一直 `ContainerCreating` | kubelet 在准备环境卡住 | 最常见是 **CNI 未就绪**、镜像拉取超时、CSI 卷 attach 慢 |
| `ImagePullBackOff/ErrImagePull` | 拉镜像失败 | 检查镜像名、registry 权限、网络出口 |
| `CrashLoopBackOff` | 容器起来就崩 | 看容器日志 `kubectl logs`；常见是应用本身错误或依赖未就绪 |
| `OOMKilled` | 内存超 limit 被 cgroup 杀 | 调大 `resources.limits.memory` 或排查内存泄漏 |

## 4.2 主线二：Pod 生命周期状态机

Pod 的 `phase` 是一个粗粒度状态机：

```text
        ┌────────── Pending ──────────┐
        │   (已写入etcd，未Running)     │
        ▼                              │
   调度成功                          调度失败/拉镜像
        │                              │
        ▼                              ▼
   ContainerCreating ────► Running ────► Succeeded (Job 完成)
        │                     │
        │                     ▼
        │                  Failed (容器退出非0且不重启)
        ▼
   持续自愈：kubelet 按 restartPolicy 重启容器
```

- **Pending**：已接受，但容器还没全跑起来（可能在调度、拉镜像、建网络）。
- **Running**：至少一个容器在运行（或正在重启）。
- **Succeeded**：所有容器成功退出且不再重启（典型是 Job）。
- **Failed**：所有容器都退出，且至少一个失败。
- **Unknown**：通常因与 kubelet 失联（节点 NotReady）。

`phase` 是粗的；细粒度看 `conditions`（`PodReady`、`PodScheduled`、`ContainersReady`、`Initialized`）和每个容器的 `state`（`waiting`/`running`/terminated`）。

### 探针（Probes）

kubelet 周期性执行三种探针来判定容器健康：

| 探针 | 用途 | 失败动作 |
|---|---|---|
| **startupProbe** | 判断容器是否启动完成（慢启动应用如大模型加载） | 失败则重启容器 |
| **livenessProbe** | 判断容器是否"活着" | 失败则**重启**容器 |
| **readinessProbe** | 判断容器是否"就绪可接流量" | 失败则从 Service Endpoints **摘除**（不重启） |

> 对 AI 推理服务极重要：模型加载可能要几分钟，用 `startupProbe`（`failureThreshold × periodSeconds` 设足够大）避免被误杀；用 `readinessProbe` 确保模型没加载完时不接流量（否则用户拿到 502）。

### restartPolicy

- `Always`（默认，Deployment/StatefulSet/DaemonSet 用）：容器退出总是重启。
- `OnFailure`（Job 常用）：失败才重启。
- `Never`：不重启。

## 4.3 主线三：Controller 的 watch → inform → reconcile

控制器不是被"调用"的，而是**主动 watch**。其运行时模型由 `client-go` 的 Informer 机制支撑：

```text
   apiserver ──watch(长连接,增量事件)──► Reflector
                                            │ list + watch
                                            ▼
                                     Delta FIFO 队列
                                            │
                                            ▼
                                   Indexer(本地缓存,可按key查)
                                            │ 触发 OnAdd/OnUpdate/OnDelete
                                            ▼
                                   Enqueue(资源 key) → WorkQueue
                                            │
                                            ▼
                                   reconcile(key)  ◄── 你的业务逻辑
                                            │
                                            ▼
                                   (必要时)写回 apiserver → 触发新事件
```

关键设计：

1. **本地缓存（Indexer）**：控制器持有一份资源的本地副本，reconcile 时读本地、不查 apiserver，大幅降低 apiserver 压力。
2. **Delta FIFO + WorkQueue**：事件去重、限速、重试。同一个 key 短时间内多次变更会被合并。
3. **resync**：即使没有任何事件，informer 也会**周期性全量 list**（默认 10 小时一次）把本地缓存与 etcd 对齐——这是"事件丢了也能自愈"的兜底。
4. **水平触发（level-triggered）而非边缘触发（edge-triggered）**：reconcile 看的是"当前状态 vs 期望状态"，不是"发生了什么事件"。这是 K8s 鲁棒性的核心——错过事件不致命，下一轮 resync 会修正。

### Deployment 控制器的 reconcile 示例

以滚动升级为例，Deployment 控制器每轮 reconcile 做的事：

```text
desired = deployment.spec.replicas              # 期望副本数
newRS = 当前版本对应的 ReplicaSet
oldRSs = 历史版本 ReplicaSet 集合

# 1. 滚动控制：在 maxSurge / maxUnavailable 约束下推进
available = newRS.availableReplicas
if available < desired:
    扩 newRS（不超过 desired + maxSurge）
# 2. 缩旧：把 oldRS 缩到 0（逐个，受 maxUnavailable 约束）
for old in oldRSs:
    scale_down(old)

# 3. 更新 status
deployment.status.updatedReplicas = ...
```

实际由 ReplicaSet 控制器负责"维持每个 RS 的副本数"，Deployment 控制器只负责"管理多个 RS 的比例"。这种**分层控制**是 K8s 的常见模式。

## 4.4 主线四：Service 与流量路由

Pod IP 会随重建而变，Service 提供稳定抽象：

```text
   用户/客户端
       │ 访问 svc.cluster.local 或 ServiceIP
       ▼
   DNS(CoreDNS) 解析 → Service ClusterIP（虚拟）
       │
       ▼
   kube-proxy 在本节点 iptables/IPVS 规则
       │ 随机/轮询 转发
       ▼
   后端某个 Pod（由 EndpointSlice 维护健康 Pod IP 列表）
```

- **EndpointSlice 控制器** watch Service 和 Pod，维护"哪些 Pod 健康、可作为后端"的列表。
- **kube-proxy** watch EndpointSlice，把 VIP→PodIP 的转发规则写到每节点内核（iptables/IPVS）。
- Pod 的 `readinessProbe` 失败 → 从 Endpoints 摘除 → kube-proxy 删规则 → 不再接流量。

> 对推理服务：`readinessProbe` 失败会"优雅摘流"，配合滚动更新可做到零中断。但要注意：iptables 模式下规则更新是全量重写，Pod 数极多时（数万）会有秒级延迟——此时用 **IPVS** 模式或 Service Mesh 的更细粒度负载均衡。

## 4.5 把四条主线串起来：一个推理服务上线的故事

假设你要上线 vLLM 推理服务，3 副本带 GPU：

1. `kubectl apply deployment(vllm, replicas=3, gpu=1)`
2. **apiserver 准入链**通过 → etcd 存 1 个 Deployment。
3. **Deployment 控制器** reconcile → 创建 1 个 ReplicaSet（replicas=3）。
4. **ReplicaSet 控制器** reconcile → 发现 0 个 Pod，创建 3 个 Pod（`nodeName=""`）。
5. **scheduler** watch 到 3 个 Pod → 经调度框架（Filter 要 GPU、Score 选负载低的）→ 绑定到 3 个 GPU 节点。
6. 各节点 **kubelet** watch 到自己的 Pod → Device Plugin 分配 GPU → CRI 起容器 → 拉镜像 → 加载模型（几分钟）。
7. **readinessProbe** 在模型加载期间失败 → 不在 Endpoints 里 → 不接流量。
8. 模型加载完 → readinessProbe 成功 → **EndpointSlice 控制器**把它加入 → **kube-proxy** 更新规则。
9. 用户访问 ServiceIP → 命中健康的 vLLM Pod。
10. 某节点宕机 → **Node 控制器** 标记 NotReady → 该 Pod 被驱逐 → ReplicaSet 控制器发现副本数 < 3 → 在别处起新 Pod → 自愈。

整个过程中，**没有任何组件"知道全局在干嘛"**——每个控制器只关心自己那一小片资源，通过 etcd 这个共享黑板协作。这就是 K8s 的"涌现式"行为：简单局部规则（控制循环 + watch）产出复杂的全局自愈能力。

## 本章小结

K8s 的运行时是**四条事件驱动主线**的交织：①Pod 从声明到 Running 的调度执行链；②Pod 生命周期状态机与探针；③Controller 的 informer + reconcile；④Service 流量路由。它们的共同根基是"水平触发的控制循环 + etcd 共享真相 + watch 事件加速"。理解了这四条主线，就能把"Pod 为什么卡 Pending""滚动更新怎么做到零中断""节点挂了怎么自愈"这些生产问题都归结到同一套模型上。

**参考来源**

- [Pod Lifecycle（phase/condition/probe/restartPolicy）](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Client-go Informer 机制 / Controller 模式](https://pkg.go.dev/k8s.io/client-go/tools/cache#Informer)
- [Service / EndpointSlice](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Scheduling Framework（调度周期 vs 绑定周期）](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/)
