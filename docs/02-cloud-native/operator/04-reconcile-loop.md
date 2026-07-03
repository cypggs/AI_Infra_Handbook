# 4. Reconcile 工作流程：一次调和的完整旅程

> 一句话理解：本章把第 2、3 章的抽象落到一个**具体、可追踪的时序**上——从"用户改了 CR 的一个字段"开始，跟着这个变化走完事件入队、Reconcile 读取、diff 计算、act、写 status、退避重试的完整旅程，并讲清每个阶段的失败模式与应对；读完你能像调试一段代码一样调试一个 Operator 的行为。

## 4.1 从"用户改了一个字段"说起

假设有一个 `InferenceService` Operator（管理 vLLM 推理服务），现状是 2 副本镜像 `vllm:0.6.3`。用户要扩容 + 升级：

```bash
kubectl patch inferenceservice llama -n prod --type merge -p \
  '{"spec":{"replicas":4,"image":"vllm:0.7.0"}}'
```

接下来发生什么？跟着这个 patch 走完整旅程。

## 4.2 阶段一：事件产生与入队

```
用户 kubectl patch
    │
    ▼
apiserver 校验（CRD schema + validating webhook）→ 写入 etcd
    │  CR 的 resourceVersion +1，generation +1
    ▼
apiserver 通过 watch 通知所有订阅者
    │
    ▼
Operator 进程里 InferenceService 的 Informer 收到 Update 事件
    │
    ▼
EventHandler（EnqueueRequestForObject）把 "prod/llama" 塞进 Workqueue
    │  （若队列里已有 "prod/llama"，去重，只保留一个）
    ▼
Workqueue 有了一个待处理项：prod/llama
```

**关键点**：

- **generation**：apiserver 给 spec 的每次改动递增 `metadata.generation`（从 1 开始）。status 的改动不递增 generation。这让 Controller 能区分"用户改了 spec"（generation 变）和"我自己写了 status"（generation 不变）。
- **去重**：用户可能在 1 秒内 patch 5 次，Workqueue 只留一个 `prod/llama`，Reconciler 只调和一次——调和到**最新**状态。这是 level-triggered 抗风暴的关键。
- **webhook 在 reconcile 之前**：若 patch 违反 validating webhook（如 replicas > 配额），apiserver 直接拒绝，根本不会进 etcd、不会触发 reconcile。

## 4.3 阶段二：Reconcile 读取

Workqueue 的 worker goroutine `pop` 出 `prod/llama`，调用 `Reconcile(ctx, Request{NamespacedName: "prod/llama"})`：

```go
func (r *InferenceServiceReconciler) Reconcile(ctx, req) (Result, error) {
    log := r.Log.WithValues("inferenceservice", req.NamespacedName)

    // 1. 读 CR（从 Cache，命中本地内存）
    var is inferencev1.InferenceService
    if err := r.Get(ctx, req.NamespacedName, &is); err != nil {
        return Result{}, client.IgnoreNotFound(err)  // CR 被删 → IgnoreNotFound，正常结束
    }
    log.Info("reconciling", "generation", is.Generation, "observedGen", is.Status.ObservedGeneration)
    // ...
```

**关键点**：

- **读走 Cache**：`r.Get` 命中本地缓存，不查 apiserver，微秒级。
- **NotFound 处理**：若 CR 不存在（被删了），返回 `IgnoreNotFound(err)`——`nil`，正常结束。这是 level-triggered 的体现：CR 没了就没啥可调和的（finalizer 逻辑会在删除阶段单独处理，见 4.7）。
- **observedGeneration 检查**：`is.Status.ObservedGeneration == is.Generation` 说明 Controller 已经处理过这版 spec；不等说明"spec 改了但我还没处理"——可用于决定是否需要 act（见 4.6）。

## 4.4 阶段三：读取所有相关子资源（算现状）

Reconciler 不能只看 CR，还要看它拥有的子资源现状：

```go
    // 2. 读所有相关子资源
    var deploy appsv1.Deployment
    err := r.Get(ctx, types.NamespacedName{Name: is.Name, Namespace: is.Namespace}, &deploy)
    deploymentExists := err == nil

    var pods corev1.PodList
    r.List(ctx, &pods, client.InNamespace(is.Namespace),
           client.MatchingLabels{"app.kubernetes.io/instance": is.Name})
    readyReplicas := countReady(pods)
```

**关键点**：

- **子资源也走 Cache**：Deployment、Pod 都从本地缓存读，极快。
- **Owner 关系靠 label + ownerReference**：找"属于这个 CR 的 Pod"用 label selector（`app.kubernetes.io/instance`），或遍历 ownerReference。两者都常用。
- **现状 = CR.spec（期望）vs 子资源实际**：`期望 replicas=4, image=0.7.0`；`现状 replicas=2, image=0.6.3, readyReplicas=2`。diff 显然不为零。

## 4.5 阶段四：act（让现状趋近期望）

根据 diff，Reconciler 决定 create/update/delete：

```go
    // 3. act
    if !deploymentExists {
        // CR 新建，子资源不存在 → 创建
        d := buildDeployment(&is)  // replicas=4, image=0.7.0
        ctrl.SetControllerReference(&is, d, r.Scheme)  // 设 owner，级联删除
        if err := r.Create(ctx, d); err != nil {
            return Result{}, err   // error → 指数退避重试
        }
        log.Info("created Deployment")
    } else {
        // 子资源存在 → 只更新需要改的字段（replicas + image）
        patch := client.MergeFrom(deploy.DeepCopy())
        deploy.Spec.Replicas = ptr.To(int32(is.Spec.Replicas))   // 2 → 4
        setContainerImage(&deploy, is.Spec.Image)                // 0.6.3 → 0.7.0
        if err := r.Patch(ctx, &deploy, patch); err != nil {
            return Result{}, err
        }
        log.Info("patched Deployment")
    }
```

**三条 act 铁律**：

1. **先查再改**：不要无条件 `Create`，先 `Get` 判断存在性——幂等性。`Patch`（基于 diff）比 `Update`（全量覆盖）更安全，不会冲掉别人改的字段。
2. **设 owner reference**：`SetControllerReference` 让子资源归 CR 所有，CR 删了子资源自动清。
3. **error 才重试**：`return Result{}, err` 触发指数退避；正常情况返回 `Result{}`（等 Pod ready 再说，见下）。

> **act 完不等于收敛**：patch 把 Deployment 改成 replicas=4，但新 Pod 还没 ready（镜像还在拉、模型还在加载）。Reconcile 此时**不该**阻塞等待，而是返回 `RequeueAfter`，让 Controller 稍后再调和检查（见 4.6）。

## 4.6 阶段五：写 status（报告实际状态）

act 之后，Reconciler 更新 CR 的 status：

```go
    // 4. 计算 + 写 status
    newStatus := inferencev1.InferenceServiceStatus{
        ObservedGeneration: is.Generation,     // 我已处理到第 N 版 spec
        ReadyReplicas:      readyReplicas,
        Ready:              readyReplicas == is.Spec.Replicas,
        Conditions:         buildConditions(readyReplicas, is.Spec.Replicas),
    }
    if !reflect.DeepEqual(is.Status, newStatus) {
        is.Status = newStatus
        if err := r.Status().Update(ctx, &is); err != nil {
            return Result{}, err   // 常见 Conflict → 重试
        }
    }
```

**关键点**：

- **`Status().Update`**：走 `/status` 子资源，单独权限。只有 status 变了才写（`DeepEqual` 判断），减少 apiserver 写入。
- **Conflict 自动重试**：若读（generation=5）和写之间别人改了 CR（generation=6），apiserver 拒绝写（`resourceVersion` 不匹配），Reconciler 返回 error，controller-runtime 指数退避重试——下一次读到最新版再处理。
- **observedGeneration**：写 status 时设 `ObservedGeneration = is.Generation`，告诉外界"我已经处理到第 N 版 spec 了"。

## 4.7 阶段六：决定是否重新入队

```go
    // 5. 是否重新入队
    if readyReplicas < is.Spec.Replicas {
        // 还没收敛（新 Pod 没 ready）→ 30s 后再检查
        return Result{RequeueAfter: 30 * time.Second}, nil
    }
    log.Info("reconciled, all ready")
    return Result{}, nil   // 收敛，等下一次外部事件
```

**Requeue 的三种语义**：

| 返回 | 含义 | 场景 |
|---|---|---|
| `Result{}, nil` | 完成，等外部事件 | 已收敛，无需主动轮询 |
| `Result{RequeueAfter: 30s}, nil` | 30s 后再调和 | 未收敛（等 Pod ready）、需要周期性检查（证书续期） |
| `Result{Requeue: true}, nil` | 立即重排（少用） | 罕见，易风暴 |
| 任意 + `error` | 指数退避重试（5s→10s→...→1000s） | act/status 失败 |

**RequeueAfter 的作用**：让 Operator 实现周期性调和，而不阻塞 worker。例如"每 5 分钟检查一次备份是否过期"，用 `RequeueAfter: 5*time.Minute`，而不是在 Reconcile 里 sleep。

## 4.8 完整时序图（收敛过程）

把 4.2-4.7 串起来，一个"扩容 + 升级"的完整收敛过程：

```
t=0   用户 patch (replicas 2→4, image 0.6.3→0.7.0)
      apiserver 写 etcd, generation 3→4
t=0.1 Informer 收到 Update → Workqueue 入 "prod/llama"
t=0.2 Reconcile #1 开始
       读 CR (gen=4, observedGen=3) → spec=4副本/0.7.0
       读 Deployment (现状 2副本/0.6.3, ready=2)
       diff != 0 → Patch Deployment (4副本/0.7.0)
       写 status (observedGen=4, readyReplicas=2, Ready=false)
       ready(2) < spec(4) → return RequeueAfter:30s
t=1   新 Pod (replica 3,4) 调度、拉镜像 0.7.0、加载模型...
t=30  Reconcile #2（被 RequeueAfter 触发）
       读 Deployment (replicas=4, 但 ready 仍=2，新 Pod 还在加载)
       diff (replicas 已对) → 不 Patch
       写 status (readyReplicas=2, Ready=false)
       ready(2) < spec(4) → return RequeueAfter:30s
t=60  新 Pod ready（模型加载完成）
t=60  Pod ready 事件 → Deployment status 变 → Owns 触发 → Workqueue 入 "prod/llama"
t=60  Reconcile #3
       读 Deployment (ready=4)
       写 status (readyReplicas=4, Ready=true, condition Ready=True)
       ready(4) == spec(4) → return Result{} (收敛！)
```

整个过程**三次 reconcile**，每次都基于当时全量状态做最小动作，从不阻塞等待。这就是 level-triggered、幂等、乐观返回的工程体现。

## 4.9 删除路径：Finalizer 的旅程

当用户 `kubectl delete inferenceservice llama`：

```
t=0   用户 delete
      apiserver 设 deletionTimestamp，但因有 finalizer "inference.io/finalizer"，不真删
t=0.1 Informer 收到 Update（deletionTimestamp 被设）→ 入队
t=0.2 Reconcile 开始
       读 CR → 发现 !DeletionTimestamp.IsZero()
       → 进入清理分支：
         归档最后一版 checkpoint 到 S3
         注销云 LB 的后端
         删除外部 DNS 记录
       清理成功 → RemoveFinalizer → Update CR
       （最后一个 finalizer 移除）→ apiserver 真正删除 CR
       （owner reference 级联 → 子 Deployment/Service 自动删）
       return Result{}, nil
```

**删除路径的三种失败**：

1. **清理逻辑失败**（S3 暂时不可达）→ return error → 退避重试 → 最终成功（S3 恢复）。**良性**。
2. **清理逻辑永远失败**（DNS 记录被别的系统锁了）→ CR 永远卡在 Terminating。**恶性**——见第 9、10 章救法。
3. **忘了移除 finalizer** → 即使清理成功，CR 也删不掉。**bug**。

## 4.10 失败模式与应对汇总

| 失败 | 表现 | 原因 | 应对 |
|---|---|---|---|
| Reconcile 永远 error | metrics `reconcile_errors_total` 持续涨，队列退避到上限 | 子资源 schema 不匹配、apiserver 限流、代码 bug | 看日志、修 bug、必要时删 CR + 重建 |
| CR 卡 Terminating | `kubectl delete` 不返回 | finalizer 清理逻辑永远失败 | `kubectl patch ... -p '{"metadata":{"finalizers":[]}}'` 强制移除（谨慎，跳过清理） |
| status 不更新 | `observedGeneration` 永远 < generation | Reconcile 在 act 前就 error 返回，没走到写 status | 修 act 的 error；或分阶段写 status |
| 操作重复执行 | 重复创建 Pod / 重复通知 | Reconcile 不幂等（没先查再改） | 所有 act 先 Get/Patch，禁止无条件 Create |
| Controller 卡死 | 队列堆积、reconcile 不前进 | Reconcile 里阻塞（sleep、长网络调用、大 List） | 长任务用 RequeueAfter；外部调用加超时 |
| 多副本同时 act | 重复创建、status 互相覆盖 | Leader Election 没开或失败 | 开 LeaderElection，检查 Lease |
| 漂移（手动改子资源被冲回） | kubectl 改 Deployment 副本数，几秒后被改回 | Controller Owns 该子资源，level-triggered 纠偏 | 这是设计行为；要改就改 CR.spec |

## 本章小结

- **一次 reconcile 六阶段**：事件入队 → 读 CR → 读子资源 → act（create/update/delete）→ 写 status → 决定是否 Requeue。
- **level-triggered 体现在全程**：每次基于全量状态算 diff，不依赖事件序列；Workqueue 去重保证事件风暴只调和一次到最新。
- **act 三铁律**：先查再改（幂等）、Patch 优于 Update、设 owner reference。
- **不阻塞**：长任务（等 Pod ready）用 `RequeueAfter` 实现"稍后再看"，Reconcile 本身必须快速返回。
- **乐观并发**：读走 Cache、写靠 `resourceVersion` 冲突重试，保证并发安全。
- **删除路径**靠 finalizer：`deletionTimestamp` 触发清理分支，成功后移除 finalizer 才真删；级联靠 owner reference。
- **常见失败**：reconcile 永续 error、CR 卡 Terminating、status 不更新、非幂等重复操作、阻塞卡死、多副本竞争——每类都有定位与应对。

**参考来源**

- [controller-runtime — Reconcile and Result](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg/reconcile)
- [client-go workqueue 退避机制](https://pkg.go.dev/k8s.io/client-go/util/workqueue)
- [Kubernetes — Finalizers](https://kubernetes.io/zh-cn/docs/concepts/overview/working-with-objects/finalizers/)
- [Kubernetes — Owners and Dependents（级联删除）](https://kubernetes.io/zh-cn/docs/concepts/architecture/garbage-collection/)
- 本手册 [Kubernetes 第 4 章](../kubernetes/04-runtime-workflow)（内置 Controller 调和时序对照）。
