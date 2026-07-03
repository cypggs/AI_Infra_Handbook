# 6. 源码分析：controller-runtime 与典型 Operator 实现

> 一句话理解：本章带你钻进 controller-runtime 的 Go 源码，沿着 `Manager.Start → Controller.Start → workqueue → Reconcile` 这条主干读完一遍真实调用链，再用三个 AI 平台代表性 Operator（KubeRay、Kubeflow Training Operator、NVIDIA GPU Operator）对照"理论如何在真实生产代码里落地"，让你从"读懂文档"升级到"读懂源码、能改源码"。

## 6.1 为什么读源码

前五章讲了 Operator 的**机制**（CRD/Controller/Reconcile/Workqueue/Informer…）。机制是"设计意图"，源码是"工程现实"。读源码的价值：

1. **破除黑盒**：知道一次 Reconcile 在哪一行代码触发退避重试，出 bug 时能定位到具体的机制。
2. **学习真实工程取舍**：生产 Operator 怎么组织 Reconcile（状态机？子 reconciler？）、怎么处理边角（部分失败、并发、版本迁移）——这些文档很少讲透。
3. **复用模式**：KubeRay 怎么算 worker 拓扑、Training Operator 怎么处理 chief 失败，都是可复用的领域建模范本。

本章主线是 **controller-runtime（`sigs.k8s.io/controller-runtime`）**——Kubebuilder/Operator SDK 的底层，绝大多数 Operator 都基于它。

## 6.2 仓库地图

controller-runtime 是个分层清晰的库，核心目录：

```
sigs.k8s.io/controller-runtime/
├── pkg/
│   ├── manager/          # Manager：进程生命周期（Cache/Client/Leader/Health/Webhook 的总装）
│   ├── cache/            # Cache：共享 informer 工厂（包装 client-go informers）
│   ├── client/           # Client：读写分离的智能客户端（读走 cache，写直通 apiserver）
│   ├── controller/       # Controller：Source→Handler→Queue→Reconciler 流水线
│   ├── handler/          # EventHandler：事件 → 队列项的映射（EnqueueForObject/ForOwner/MapFunc）
│   ├── source/           # Source：watch 什么（Kind）
│   ├── internal/         # workqueue 包装、event handlers 内部实现
│   ├── reconcile/        # Reconcile 接口定义 + Result 语义
│   ├── webhook/          # admission/conversion webhook server
│   ├── leader/           # leader election（基于 coordination.k8s.io/Lease）
│   ├── metrics/          # Prometheus 指标注册
│   └── healthz/          # liveness/readiness
└── fake/                 # 测试用 fake client
```

读源码的主干顺序：`manager` → `controller` → `internal/workqueue` → `reconcile`。

## 6.3 主干调用链：Manager.Start

Operator 进程入口（简化自 KubeRay main.go）：

```go
func main() {
    mgr, _ := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
        Scheme: scheme, LeaderElection: true, LeaderElectionID: "ray-operator",
        Metrics: server.Options{BindAddress: ":8080"},
        HealthProbeBindAddress: ":8081",
    })
    (&controllers.RayClusterReconciler{Client: mgr.GetClient(), Scheme: mgr.GetScheme()}).
        SetupWithManager(mgr)
    ctrl.NewControllerManagedBy(mgr).
        For(&rayv1.RayCluster{}).
        Owns(&appsv1.Deployment{}).
        Complete(...)
    mgr.Start(ctrl.SetupSignalHandler())
}
```

`mgr.Start` 做的事（`pkg/manager/internal.go`）：

```go
func (cm *controllerManager) Start(ctx) error {
    // 1. 启动 Cache（所有 informer 开始 List+Watch）
    cm.startCache(ctx)            // → cache.Start → 各 informer.Run
    // 2. 等 Cache 同步完成（hasSynced == true），否则标记 not-ready
    if !cm.waitForCacheSync(ctx) { return errors.New("cache sync failed") }
    // 3. Leader Election：抢 Lease，抢到才继续
    cm.startLeaderElection(ctx)
    // 4. 启动所有 Controller（cm.runnables）
    for _, c := range cm.controllers { go c.Start(ctx) }
    // 5. 启动 webhook server（若有）、metrics、health server
    cm.startWebhookServer(ctx)
    cm.serveMetrics(ctx); cm.serveHealthz(ctx)
    // 6. 阻塞直到 ctx 取消（收到 SIGTERM）
    <-ctx.Done()
}
```

**三个关键时序**：

- **Cache 先于 Controller**：Controller 读资源依赖 Cache，必须先同步完。
- **waitForCacheSync 是 readiness 闸门**：Cache 没同步完，进程不 ready，K8s 不摘流——避免"启动初期读到空数据"。
- **Leader Election 在 Controller 前**：非 leader 副本不会启动 Controller（不 reconcile），但进程仍存活（响应 webhook/metrics）。

## 6.4 Controller.Start：流水线启动

`pkg/controller/controller.go` 的 `Start`：

```go
func (c *Controller) Start(ctx) error {
    // 1. 创建 workqueue（默认 rate limited，带指数退避）
    c.Queue = workqueue.NewRateLimitingQueue(rateLimiter)
    // 2. 启动 Source（For/Owns 的 informer），把事件通过 EventHandler 接到 Queue
    for _, src := range c.Sources {
        src.Start(ctx, c.Queue, c.EventHandler)  // informer 事件 → handler → Queue.Add
    }
    // 3. 启动 N 个 worker goroutine（默认 1，可配 MaxConcurrentReconciles）
    for i := 0; i < c.MaxConcurrentReconciles; i++ {
        go wait.UntilWithContext(ctx, c.worker, time.Second)
    }
    return nil
}

func (c *Controller) worker(ctx) {
    for c.processNextWorkItem(ctx) {}   // 死循环：不断 pop 队列
}

func (c *Controller) processNextWorkItem(ctx) bool {
    obj, shutdown := c.Queue.Get()        // 阻塞取
    defer c.Queue.Done(obj)
    req := obj.(reconcile.Request)
    // 调用开发者写的 Reconcile
    result, err := c.Reconcile.Reconcile(ctx, req)
    switch {
    case err != nil:
        c.Queue.AddRateLimited(req)       // 指数退避重试
    case result.RequeueAfter > 0:
        c.Queue.Forget(obj); c.Queue.AddAfter(req, result.RequeueAfter)  // 定时重排
    case result.Requeue:
        c.Queue.AddRateLimited(req)
    default:
        c.Queue.Forget(obj)               // 收敛，丢弃
    }
    return true
}
```

这段代码精确定义了第 4、5 章讲的 Requeue 语义：**error → 退避、RequeueAfter → 定时、Requeue → 立即、else → 结束**。`AddRateLimited` 内部用 `ItemExponentialFailureRateLimiter`，退避序列 `5s → 10s → 20s → ... → 1000s`（上限 `baseDelay * 2^maxFailures`，被 `maxDelay` 截断）。

## 6.5 事件 → 队列：EventHandler

`For(&RayCluster{})` 注册的 handler 是 `EnqueueRequestForObject`（`pkg/handler/enqueue.go`）：

```go
func (e *EnqueueRequestForObject) Create(e event.CreateEvent, q workqueue.RateLimitingInterface) {
    q.Add(reconcile.Request{NamespacedName: types.NamespacedName{Name: e.Object.GetName(), Namespace: ...}})
}
// Update/Delete 同理
```

`Owns(&Deployment{})` 注册的是 `EnqueueRequestForOwner`——关键在**反查 ownerReference**，把子资源事件映射到 owner CR：

```go
func (e *EnqueueRequestForOwner) Update(e event.UpdateEvent, q ...) {
    owner := metav1.GetControllerOf(e.ObjectNew)   // 读 metadata.ownerReferences[?].controller==true
    if owner == nil { return }
    q.Add(reconcile.Request{NamespacedName: {Name: owner.Name, Namespace: e.ObjectNew.GetNamespace()}})
}
```

这就解释了第 3.5 节的机制：**子资源变 → handler 读它的 ownerReference → 把 owner CR 的 ns/name 入队 → 触发 owner 的 reconcile**。owner reference 是"事件回流到 owner"的桥梁。

> **重要推论**：若子资源没设 ownerReference（Reconciler 忘了 `SetControllerReference`），`GetControllerOf` 返回 nil，子资源变化**不会触发** owner reconcile——这正是第 5.3 节"漏 Owns / 漏设 owner"导致自愈失效的根因。

## 6.6 退避重试的精确语义

`pkg/internal/controller/rate_limiter.go` 默认用组合限流器：

```go
func DefaultControllerRateLimiter() workqueue.RateLimiter {
    return workqueue.NewMaxOfRateLimiter(
        workqueue.NewItemExponentialFailureRateLimiter(5*time.Millisecond, 1000*time.Second),
        &workqueue.BucketRateLimiter{Limiter: rate.NewLimiter(rate.Limit(10), 100)},
    )
}
```

- **指数退避**：`5ms → 10ms → 20ms → ... → 1000s`（取两者 max）。
- **全局令牌桶**：整体 10 QPS + burst 100，防止退避恢复时瞬间风暴。

> **调优**：API 限流严重的场景（如大集群），可换更激进的限流器或自定义 per-key 退避。controller-runtime 允许通过 `ControllerManagedBy(mgr).WithOptions(controller.Options{RateLimiter: ...})` 注入自定义限流器。

## 6.7 Client 读写分离的实现

`pkg/client/split.go`（简化）：

```go
type client struct {
    cache  Reader          // 读走 cache
    direct Client          // 写直通 apiserver
}

func (c *client) Get(ctx, key, obj) error { return c.cache.Get(ctx, key, obj) }       // 缓存
func (c *client) List(ctx, list, opts...) error { return c.cache.List(...) }          // 缓存
func (c *client) Create(ctx, obj, opts...) error { return c.direct.Create(...) }      // apiserver
func (c *client) Update(ctx, obj, opts...) error { return c.direct.Update(...) }      // apiserver
func (c *client) Patch(ctx, obj, patch, opts...) error { return c.direct.Patch(...) } // apiserver
func (c *client) Status() StatusWriter { return c.direct.Status() }                   // /status 子资源
```

**`resourceVersion` 乐观锁**：`Update`/`Patch` 把对象的 `metadata.resourceVersion` 带给 apiserver，apiserver 检查若与 etcd 现存的不一致，返回 `409 Conflict`。controller-runtime 把 Conflict 当成可重试错误——Reconciler 返回 error → workqueue 退避 → 下次读到最新版重试。这保证"读后写"并发安全。

`Status().Update` 走 `/status` 子资源：apiserver 对 spec 和 status 用**独立的 resourceVersion**，写 status 不触发 spec 的 reconcile（避免死循环——Reconcile 写 status → status 变 → 又触发 Reconcile）。

## 6.8 典型 Operator 源码对照（一）：KubeRay

[KubeRay](https://github.com/ray-project/kubebuilder)（`ray-project/kuberay`）是 Ray on K8s 的事实标准，管理 `RayCluster`/`RayService`/`RayJob`。它的 Reconciler 是"领域建模教科书"：

```
api/core/v1alpha1/raycluster.go        # CRD 定义（RayClusterSpec/Status）
controllers/raycluster_controller.go   # Reconciler 入口
controllers/raycluster_controller.go:
  Reconcile(ctx, req):
    rc = getCluster()
    if deleting: return r.deleteRayCluster(...)        # finalizer 分支
    config := desiredConfig(rc)                         # 期望拓扑（head + workers + svc）
    r.reconcileServices(rc, config)                     # 子 reconciler：Service
    r.reconcileHeadPod(rc, config)                      # 子 reconciler：head Pod
    r.reconcileWorkerPods(rc, config)                   # 子 reconciler：worker Pods
    r.updateStatus(rc, config)                          # 写 status
    return RequeueAfter(5min)                           # 周期 reconcile（autoscaler）
```

**可学习的模式**：

- **子 reconciler 拆分**：Reconcile 主干只编排，每个子资源（Service/head/worker）一个 `reconcile*` 函数，各自幂等、各自返回是否修改。大型 Operator 几乎都这样拆。
- **desiredConfig 先算后比**：先把"期望状态"算成内存对象，再逐个和现状比（create/update/不动），保证幂等。
- **RequeueAfter 周期 reconcile**：Ray 的 autoscaler 需要周期决策，KubeRay 用 `RequeueAfter: 5min`（而非纯靠事件）——这是"事件驱动 + 周期兜底"的常见组合。
- **Pod 级而非 Deployment 级管理**：KubeRay 直接管 Pod（不经过 Deployment/StatefulSet），因为 Ray 对 Pod 生命周期有领域知识（节点注册、对象存储 spill）。这打破了"Operator 管 Deployment"的默认假设——**Operator 可以管任意资源粒度，只要领域需要**。

## 6.9 典型 Operator 源码对照（二）：Kubeflow Training Operator

[Training Operator](https://github.com/kubeflow/training-operator)（`kubeflow/training-operator`）管理分布式训练作业（`PyTorchJob`/`TFJob`/`MPIJob`/`PaddleJob`/`XGBoostJob`）。核心难点是**多角色协调**（chief/worker/ps）。

```
pkg/controller.v1/common/    # 通用 reconcile 框架（所有 job 类型共享）
pkg/controller.v1/pytorch/   # PyTorch 特定逻辑
```

**关键设计**：

- **GenericJobReconciler**：把"列出所有角色 Pod、按状态机推进、算期望副本、协调 PVC/Service"抽象成通用层，各 job 类型只实现"哪些角色、启动命令模板"。这是**DRY 处理多 CRD**的范本——当你有 N 个相似 CRD，别复制 N 份 Reconciler，抽通用层。
- **Policy（重启策略）**：`spec.pytorchReplicaSpecs.Worker.restartPolicy` 控制 chief/worker 夌败后是 `Always`（重启）、`OnFailure`（重试有限次）、`Never`（不重启）。Reconcile 据此决定"重建 Pod 还是标记作业失败"。
- **RunPolicy + Suspend**：支持 `spec.runPolicy.suspendSeconds` 把作业挂起（缩到 0 副本保留 spec），resume 时恢复——AI 场景常见（夜间挂起省 GPU）。
- **活跃截止时间** `activeDeadlineSeconds`：超时自动标记 Failed 并清理，防止卡死作业占 GPU。

> **领域教训**：分布式训练的"完成"判断很微妙（chief 成功就算成功，还是所有 worker 退出？）。Training Operator 为每种 job 类型写了明确的 `IsSucceeded`/`IsFailed` 状态机——**status.phase 的语义必须领域精确**，不能含糊。

## 6.10 典型 Operator 源码对照（三）：NVIDIA GPU Operator

[GPU Operator](https://github.com/NVIDIA/gpu-operator)（`NVIDIA/gpu-operator`）管理 GPU 节点的全栈：驱动、container toolkit、DCGM exporter、MIG 配置、node-labeler、driver-upgrade。它的特点是**DaemonSet + 节点级协调**。

```
controllers/state_manager.go       # 每个 GPU 相关组件一个 state reconciler
controllers/driver.go              # nvidia-driver DaemonSet 的 reconcile
controllers/toolkit.go             # container-toolkit DaemonSet
controllers/dcgmexporter.go        # 监控 exporter
controllers/validator.go           # 节点就绪校验
```

**关键设计**：

- **state reconciler 注册表**：`GPUOperator` CR 触发后，`StateManager` 遍历所有已注册的 component reconciler（driver/toolkit/dcgm/...），每个独立调和自己的 DaemonSet。新增组件只需注册一个 reconciler，不改主干——**开闭原则**。
- **节点就绪判断**：GPU 节点就绪不是"DaemonSet ready=1"，而是"校验 Pod 通过"（跑 CUDA 自检）。GPU Operator 起一个 validator DaemonSet，只有它成功才算节点 GPU 可用——**领域就绪 ≠ K8s 就绪**，要自建探针。
- **驱动版本与节点内核匹配**：driver DaemonSet 要选对应当前内核的驱动镜像，节点升级内核时自动重调和换驱动——这是 Operator 处理"硬件 + OS"复杂耦合的实战。

## 6.11 三大 Operator 对比

| 维度 | KubeRay | Training Operator | GPU Operator |
|---|---|---|---|
| 管理对象 | Ray 集群（长跑） | 训练作业（有头有尾） | GPU 节点栈（节点级） |
| 子资源粒度 | **Pod 级**（绕过 Deployment） | Pod + Service + ConfigMap | **DaemonSet 级** |
| 终止语义 | 长跑，无"完成" | 精确 Succeeded/Failed 状态机 | 节点就绪（validator） |
| 周期 reconcile | 5min（autoscaler） | 事件驱动为主 | 事件驱动 |
| 复杂度焦点 | 拓扑 + 弹性 | 多角色协调 + 重启策略 | 组件组合 + 硬件耦合 |
| 可学模式 | 子 reconciler 拆分 | 通用层抽象多 CRD | 注册表 + 开闭原则 |

## 6.12 从源码提炼的工程要点

读完 controller-runtime + 三个生产 Operator，提炼几条可复用的工程准则：

1. **Reconcile 要短**：读主干 + 编排子 reconciler，每个子 reconciler 干一件事、幂等返回。超过 200 行的 Reconcile 几乎都该拆。
2. **先算 desired 再 diff**：把期望状态算成内存对象，再逐字段比现状——这是幂等的工程保障，比"边读边改"安全得多。
3. **事件驱动 + 周期兜底**：用事件保证响应性，用 `RequeueAfter` 周期兜底（防漏事件、做 autoscaler/续期）。两者组合是生产常态。
4. **status.phase 要领域精确**：模糊的 phase（如只写 Running）会害死上层编排。状态机要覆盖 Creating/Running/Scaling/Upgrading/Failed/Succeeded。
5. **领域就绪 ≠ K8s 就绪**：Pod ready 不代表应用就绪（模型没加载、节点 GPU 没校验）。要自建健康探针写进 status.condition。
6. **复用通用层**：多 CRD 相似时抽通用 reconciler（Training Operator），多组件相似时用注册表（GPU Operator）。
7. **owner reference 是自愈的命脉**：每个你创建的子资源都要 `SetControllerReference` + 在 `Owns` 注册，否则自愈失效。

## 本章小结

- **主干调用链**：`Manager.Start`（启 Cache→同步→Leader Election→启 Controller→启 webhook/metrics）→ `Controller.Start`（启 Source→启 N worker→worker 死循环 pop queue→调 Reconcile）→ Reconcile 返回决定（退避/定时/立即/结束）。
- **EventHandler 反查 ownerReference** 是子资源事件回流到 owner CR 的机制；漏设 owner = 自愈失效。
- **退避重试**：`ItemExponentialFailureRateLimiter`（5ms→1000s）+ 全局令牌桶；可注入自定义限流器。
- **Client 读写分离**：读走 Cache、写直通 apiserver，靠 `resourceVersion` 乐观锁 + Conflict 重试保证并发安全；`/status` 子资源独立 resourceVersion，避免写 status 死循环。
- **三大 AI Operator** 各自示范了关键模式：KubeRay（Pod 级 + 子 reconciler + 周期 reconcile）、Training Operator（通用层抽象多 CRD + 精确状态机 + 重启策略）、GPU Operator（注册表 + 开闭原则 + 领域就绪探针）。
- **可复用准则**：Reconcile 要短、先算 desired 再 diff、事件+周期兜底、status 精确、领域就绪自建探针、复用通用层、owner reference 保命。

**参考来源**

- [controller-runtime 源码（GitHub）](https://github.com/kubernetes-sigs/controller-runtime)
- [KubeRay 源码](https://github.com/ray-project/kubebuilder) / [KubeRay Reconciler](https://github.com/ray-project/kubebuilder/blob/main/controllers/raycluster_controller.go)
- [Kubeflow Training Operator 源码](https://github.com/kubeflow/training-operator)
- [NVIDIA GPU Operator 源码](https://github.com/NVIDIA/gpu-operator)
- [client-go workqueue 限流器](https://pkg.go.dev/k8s.io/client-go/util/workqueue)
- 本手册 [Kubernetes 第 6 章](../kubernetes/06-source-analysis)（informer 源码，controller-runtime Cache 的底层）。
