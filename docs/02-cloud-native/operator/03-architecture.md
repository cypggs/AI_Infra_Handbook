# 3. 架构设计：controller-runtime 全景

> 一句话理解：现代 Operator 几乎都用 **controller-runtime**（Kubebuilder/Operator SDK 的底层）构建，它的架构可以拆成两层——**Manager（管理进程生命周期：cache、client、leader election、metrics、health）** 和 **Controller（管理一个 reconcile 循环：Source → EventHandler → Workqueue → Reconciler）**；理解这十几个组件的协作，你就理解了任何一个生产 Operator 的运行时。

## 3.1 全景图

一个 controller-runtime Operator 进程的内部结构：

```
┌──────────────────────────────── Operator 进程（一个 Deployment，多副本） ────────────────────────────────┐
│                                                                                                            │
│   ┌──────────────────────── Manager（ctrl.NewManager）────────────────────────┐                            │
│   │                                                                            │                            │
│   │   ┌──────────── Cache（共享 informer 工厂）─────────────┐                  │                            │
│   │   │  RayCluster informer   Deployment informer   Service informer  ...     │     watch/list             │
│   │   │   ├── List (全量)  ──┐   ├── List ──┐          ├── List ──┐            │ ◄────────────────────►     │
│   │   │   └── Watch (增量) ──┤   └── Watch ─┤          └── Watch ─┤            │        apiserver/etcd      │
│   │   │      (本地 ThreadSafeStore 缓存)      │               │     │            │                            │
│   │   └──────────────────────────────────────┘               │     │            │                            │
│   │                                                            │     │            │     write back              │
│   │   ┌──────────── Client（读走 Cache，写直通 apiserver）──┐  │     │            │ ◄────────────────────►     │
│   │   │  r.Get / r.List   → 命中 Cache（快、不压 apiserver） │◄─┘     │            │        apiserver/etcd      │
│   │   │  r.Create/Update/Delete → 直达 apiserver             │        │            │                            │
│   │   │  r.Status().Update → /status 子资源                  │        │            │                            │
│   │   └──────────────────────────────────────────────────────┘        │            │                            │
│   │                                                                    │            │                            │
│   │   ┌── Controller A (RayCluster) ──┐    ┌── Controller B (...) ──┐ │            │                            │
│   │   │  Source: For(RayCluster)      │    │  ...                   │ │            │                            │
│   │   │   └─► EventHandler            │    │                        │ │            │                            │
│   │   │         └─► 入 Workqueue      │    │                        │ │            │                            │
│   │   │  Source: Owns(Deployment)     │    │                        │ │            │                            │
│   │   │   └─► 映射到 owner CR → 入队  │    │                        │ │            │                            │
│   │   │  ┌── Workqueue ──┐            │    │                        │ │            │                           
│   │   │  │ ns/name 去重  │ ──pop──► Reconciler(req) ──► Result       │ │            │                            │
│   │   │  │ 指数退避重试  │            │    │                        │ │            │                            │
│   │   │  └───────────────┘            │    │                        │ │            │                            │
│   │   └────────────────────────────────┘    └────────────────────────┘ │            │                            │
│   │                                                                    │            │                            │
│   │   Leader Election（多副本只一个干活）  │  Metrics（/metrics） │  Webhook Server  │                            │
│   │   Healthz / Readyz                     │  (Prometheus)        │  (:9443)         │                            │
│   └────────────────────────────────────────────────────────────────────────────────┘                            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

下面逐层拆解。

## 3.2 Manager：进程的大管家

`ctrl.NewManager(config, ctrl.Options{...})` 创建一个 Manager，它是整个 Operator 进程的容器，负责：

1. **创建并持有 Cache 和 Client**（所有 Controller 共享，避免重复 watch）。
2. **管理 Controller 生命周期**：`SetupWithManager(mgr)` 把 Controller 注册进来，`mgr.Start(ctx)` 启动所有 Controller 的 goroutine。
3. **Leader Election**：多副本部署时，用 Lease（租约）保证只有一个副本真正干活，其他待命。
4. **Metrics / Health 端点**：暴露 `/metrics`（Prometheus）、`/healthz`、`/readyz`（liveness/readiness）。
5. **Webhook Server**：若 Operator 含 admission webhook，Manager 启动一个 HTTPS server（默认 `:9443`）接收 apiserver 的准入回调。

```go
func main() {
    mgr, _ := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
        Scheme:                  scheme,
        Metrics:                 server.Options{BindAddress: ":8080"},
        HealthProbeBindAddress:  ":8081",
        LeaderElection:          true,
        LeaderElectionID:        "ray-operator.io",
    })
    // 注册 Controller
    (&RayClusterReconciler{Client: mgr.GetClient(), Scheme: mgr.GetScheme()}).
        SetupWithManager(mgr)
    // 注册 webhook
    (&RayCluster{}).SetupWebhookWithManager(mgr)
    mgr.AddHealthzCheck("healthz", healthz.Ping)
    mgr.Start(ctrl.SetupSignalHandler())
}
```

> **为什么所有 Controller 共享一个 Manager/Cache**：一个 Operator 进程常含多个 Controller（如 KubeRay 有 RayCluster + RayService + RayJob），它们 watch 的资源有重叠。共享 Cache 避免对 apiserver 发起重复 watch（watch 是有成本的），这是 controller-runtime 的一个重要优化。

## 3.3 Cache 与 Informer：本地缓存 + watch

Cache 包装了 client-go 的 **Informer** 机制（见 [K8s 第 6 章](../kubernetes/06-source-analysis)），为每种 watch 的资源维护一份**本地缓存**：

```
apiserver ──List(全量)──► Informer ──► ThreadSafeStore（内存里的 map）
          ──Watch(增量)──►  (Add/Update/Delete 事件) ──► 触发 EventHandler
```

- **启动时**：`List` 拉一份全量进缓存（这是"建立基线"）。
- **运行时**：`Watch` 接收增量事件，更新缓存，同时分发给注册的 EventHandler。
- **断线重连**：watch 断了，Informer 自动重新 List + Watch 重建缓存（这个过程可能丢一些中间事件，但 level-triggered 的 Reconcile 不在乎——它每次读全量）。

**Cache 的意义**：

1. **Reconciler 读资源走本地内存**（`r.Get` 命中 Cache），极快、不压 apiserver。一个频繁 reconcile 的 Operator 若每次都直查 apiserver，会把 apiserver 打爆。
2. **watch 解耦**：Reconciler 不直接 watch，而是 Informer watch 后把"哪个 CR 变了"塞进 Workqueue，Reconciler 只管处理队列。

## 3.4 Client：读写分离（读走 Cache，写直通）

controller-runtime 的 `client.Client` 是一个**智能读写分离**的接口：

| 操作 | 路径 | 原因 |
|---|---|---|
| `Get` / `List` | **Cache（本地内存）** | 快、不压 apiserver；最终一致（缓存有几秒延迟可接受） |
| `Create` / `Update` / `Delete` | **直通 apiserver** | 写必须落 etcd 才生效 |
| `Status().Update` | apiserver 的 `/status` 子资源 | 单独权限、不触发 spec 的 reconcile |

**关键细节——读后写的一致性**：Reconciler 从 Cache 读到的是"几秒前的快照"，写入用 apiserver 的**乐观并发**（基于 `resourceVersion`）。如果在你读和写之间别人改了对象，你的 `Update` 会被 apiserver 拒（`Conflict`），controller-runtime 自动重试——这保证不会"覆盖别人的改动"。

> **这正是 Helm 三方合并要解决的同类问题**（见 [Helm 第 3 章](../helm/03-architecture)）：多个写者并发改同一对象时如何不互相覆盖。K8s 的答案是 `resourceVersion` 乐观锁 + 冲突重试；Helm 的答案是三方合并 patch。场景不同，目标一致。

## 3.5 Controller：Source → EventHandler → Workqueue → Reconciler

一个 Controller 由四个组件串成一个流水线：

### Source（事件源）

Source 告诉 Controller "watch 什么"。最常见的是 `source.Kind`（watch 某种资源）：

- `For(&RayCluster{})`：主资源，每个事件映射到它自己（`ns/name`）。
- `Owns(&Deployment{})`：子资源，事件**映射到它的 owner CR**（通过 ownerReference 反查）——这样子资源变 → 触发 owner CR 的 reconcile。

也可以 watch 外部资源（`Watches(&ExternalCR{}, handler)`），用自定义映射函数把外部事件翻译成"该调和哪个 CR"。

### EventHandler（事件 → 队列项）

EventHandler 决定"一个资源事件，该把哪些 `ns/name` 入队"。默认 handler：

- `EnqueueRequestForObject`：把对象自己入队（用于主资源）。
- `EnqueueRequestForOwner`：把对象的 owner 入队（用于 Owns 的子资源）。
- `EnqueueRequestsFromMapFunc`：用函数把事件映射成 0~N 个队列项（用于跨资源 watch，如"ConfigMap 变了 → 重新调和所有引用它的 CR"）。

### Workqueue（去重 + 退避重试的工作队列）

这是 controller-runtime 包装 client-go `workqueue` 的产物，三个关键特性：

1. **去重**：队列里存的是 `ns/name` 字符串。同一个 key 短时间内入队多次，只会处理一次（避免事件风暴把 Reconciler 淹没）。
2. **有序 + 有延迟**：可以指定 `AddAfter(key, 30s)`（对应 `Result{RequeueAfter: 30s}`），30 秒后才处理。
3. **指数退避**：Reconcile 返回 error 时，该 key 会被按指数退避重新入队（5s, 10s, 20s, 40s ... 上限 1000s），避免对 apiserver 的错误风暴。

> **去重的精妙**：K8s 资源变化可能极快（一个 Deployment 短时间内 spec 改 10 次），但 level-triggered 的 Reconciler 只需要"调和到最新状态"一次。Workqueue 的去重保证：不管中间多少事件，最终只 reconcile 一次到最新状态——这是 level-triggered 模型能扛住事件风暴的工程基础。

### Reconciler（业务逻辑）

`Reconcile(ctx, req) (Result, error)`——开发者唯一需要写的部分（见第 2.3 节四条铁律）。返回值：

- `Result{Requeue: true}`：立即重新入队（少用，易风暴）。
- `Result{RequeueAfter: 30s}`：30 秒后再调和（用于轮询未收敛状态，如等 Pod ready）。
- `Result{}` + `nil error`：完成，等下一次外部事件。
- 任意 `error`：指数退避重试。

## 3.6 Leader Election：多副本只有一个干活

Operator 通常部署多副本（高可用）。但若所有副本都 reconcile，会**重复操作**（重复创建 Pod、status 互相覆盖）。Leader Election 用一个 K8s **Lease** 资源做分布式锁：

- 启动时各副本争抢 `ray-operator.io` 这个 Lease。
- 抢到的成为 leader，启动所有 Controller；其他副本待命（保持进程存活但不 reconcile）。
- Leader 心跳续约（默认每 2s），断网/崩溃导致续约失败 → 其他副本接管。

```yaml
# Operator Deployment 通常 2 副本 + Manager 开 LeaderElection
spec:
  replicas: 2
```

> **注意**：Leader Election 保证"只有一个副本 reconcile"，但所有副本的进程都活着（webhook server 在所有副本都响应）。这和 K8s 内置 Controller Manager 的 leader election 机制完全一样。

## 3.7 Metrics、Health、Webhook Server

- **Metrics**（`:8080/metrics`）：controller-runtime 自动暴露一组 Prometheus 指标——`controller_runtime_reconcile_total`（reconcile 次数）、`controller_runtime_reconcile_errors_total`（失败次数）、`workqueue_depth`（队列深度）、`reconcile_time_seconds`（耗时）。**这些是 Operator 可观测性的核心**（见第 8 章）。
- **Health**（`:8081`）：`/healthz`（liveness，进程活着）、`/readyz`（readiness，Cache 同步完成可服务）。K8s 据此重启/摘流。
- **Webhook Server**（`:9443`）：若 Operator 含 admission/conversion webhook，Manager 启一个 HTTPS server，apiserver 带证书回调它。证书管理是生产痛点（见第 8 章）。

## 3.8 与 K8s 内置 Controller 的同构性

把上面的架构和 [K8s 第 3 章](../kubernetes/03-architecture) 的 kube-controller-manager 对照：

| 组件 | K8s 内置 Controller | controller-runtime Operator |
|---|---|---|
| 进程管理 | cloud-provider / controller-manager | Manager |
| watch 缓存 | informer factory | Cache（共享 informer） |
| 读写 API | client-go client | Client（读写分离） |
| 事件 → 队列 | informer + workqueue | Source + EventHandler + Workqueue |
| 业务逻辑 | 各 Controller 的 syncHandler | Reconciler |
| 选举 | leader election（如 kube-scheduler） | Leader Election（Lease） |
| 指标 | /metrics | /metrics（同一套） |

**几乎一一对应**。这再次说明：**Operator 不是新发明，而是 K8s 控制平面能力对用户的开放**。K8s 把自己的 Controller 构造工具（client-go informer/workqueue）封装成 controller-runtime，让用户用同样的模式写"自己的 Deployment Controller"。

## 本章小结

- **Manager** 是进程大管家：持有共享 Cache/Client、管理 Controller 生命周期、Leader Election、Metrics/Health/Webhook Server。
- **Cache（Informer）** 为每种 watch 的资源维护本地缓存，Reconciler 读资源走内存（快、不压 apiserver），靠 List+Watch+自动重连保持一致。
- **Client 读写分离**：读走 Cache，写直通 apiserver，写靠 `resourceVersion` 乐观锁 + 冲突重试保证并发安全。
- **Controller 流水线**：Source（watch 什么）→ EventHandler（事件映射成 ns/name）→ Workqueue（去重 + 退避）→ Reconciler（业务逻辑）。去重是 level-triggered 抗事件风暴的基础。
- **Leader Election**：多副本只有一个 reconcile，靠 Lease 租约，和 K8s 内置机制一致。
- **Metrics/Health/Webhook** 是生产可观测与准入控制的基础设施。
- **同构性**：controller-runtime 几乎与 K8s 内置 Controller 一一对应——Operator 是 K8s 控制平面能力对用户的开放。

**参考来源**

- [controller-runtime 架构文档](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg)
- [Kubebuilder Book — Controller Runtime](https://book.kubebuilder.io/cronjob-tutorial/controller-implementation)
- [client-go Informer 机制](https://pkg.go.dev/k8s.io/client-go/informers)
- 本手册 [Kubernetes 第 3 章](../kubernetes/03-architecture)（kube-controller-manager 同构）、第 6 章（informer 源码）、[Helm 第 3 章](../helm/03-architecture)（并发写的乐观锁对比）。
