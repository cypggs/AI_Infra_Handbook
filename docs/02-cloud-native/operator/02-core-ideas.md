# 2. 核心思想：CRD、Controller 与 Reconcile 调和循环

> 一句话理解：Operator 的全部思想可以压缩成三件事——**① CRD 给你一种"自定义 K8s 资源"的能力（扩展 API），② Controller 是一个永远在线、watch 这些资源的进程，③ Reconcile 是一个"读现状 → 算 diff → act 让现状等于期望"的纯函数**；围绕这三件套，还有 finalizer（删除前清理）、owner reference（级联回收）、status（报告状态）、webhook（准入校验）四个配套概念。本章把这套心智模型一次讲透。

## 2.1 CRD 与 CR：扩展 Kubernetes API

### CRD（CustomResourceDefinition）—— 定义资源类型

CRD 本身是一个 K8s 资源（`apiVersion: apiextensions.k8s.io/v1`），它告诉 apiserver："从现在起，集群里多了一种叫 `RayCluster` 的资源"。定义之后，apiserver 会**自动**为它生成 RESTful API（`/apis/ray.io/v1/namespaces/ns/rayclusters/`）、存进 etcd、支持 `kubectl get raycluster`、受 RBAC 保护——和内置资源一模一样。

一个 CRD 的骨架：

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: rayclusters.ray.io            # <复数>.<group>
spec:
  group: ray.io                       # API group
  names:
    kind: RayCluster                  # kubectl get raycluster
    plural: rayclusters
    singular: raycluster
    shortNames: [rayc]                # kubectl get rayc
  scope: Namespaced                   # 或 Cluster
  versions:
    - name: v1
      served: true
      storage: true                   # 只有一个版本负责写 etcd
      schema:
        openAPIV3Schema:              # 用 OpenAPI v3 校验 spec
          type: object
          properties:
            spec:
              type: object
              properties:
                headReplicas: { type: integer, minimum: 1 }
                workerReplicas: { type: integer, minimum: 0 }
                image: { type: string }
            status:                   # status 由 Controller 写
              type: object
              properties:
                ready: { type: boolean }
                workerReady: { type: integer }
      subresources:
        status: {}                    # 启用 /status 子资源
        scale:                        # 启用 kubectl scale
          specReplicasPath: .spec.workerReplicas
          statusReplicasPath: .status.workerReady
```

**关键设计点**：

- **OpenAPI v3 schema**：CRD 的 `spec` 字段必须有 schema 校验（v1 起强制）。这让"CR 写错"在 apiserver 层就被拒，而不是进到 Controller 才报错——这和 Helm 的 `values.schema.json`（见 [Helm 第 9 章](../helm/09-best-practices)）思路一致。
- **多版本 + 转换**：CRD 可声明 `v1alpha1`/`v1beta1`/`v1` 多版本同时 served，配 conversion webhook 互转。这让 CRD 能**平滑演进**（见第 8 章）。
- **`spec` vs `status` 分离**：`spec` 是用户写的"期望状态"（不可变语义由 Controller 保证），`status` 是 Controller 写的"实际状态"。这是 K8s 声明式 API 的核心约定——和 Deployment 的 `spec.replicas` / `status.readyReplicas` 完全同构。
- **subresources**：`status: {}` 启用 `/status` 子资源（Controller 通过它单独更新 status，不触发 spec 变化引发的 reconcile）；`scale` 启用 `kubectl scale` 对接 HPA。

### CR（Custom Resource）—— 资源实例

定义了 CRD 后，用户创建 CR（实例）：

```yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: my-ray
  namespace: prod
spec:                       # 期望状态（用户写）
  headReplicas: 1
  workerReplicas: 4
  image: rayproject/ray:2.9.0
status:                     # 实际状态（Controller 写，用户别动）
  ready: false
  workerReady: 0
```

```bash
kubectl get raycluster my-ray -n prod -o yaml
kubectl get rayc -A                       # 短名也行
```

**心智模型**：CRD 是"类"，CR 是"对象"。CR 进 etcd，apiserver 像对待 Pod 一样对待它。Controller 通过 watch/list CR 来感知用户意图。

## 2.2 Controller：永远在线的 watch 循环

Controller 是一个跑在集群里（通常是个 Deployment，多副本 + leader election）的进程。它的核心职责是：

> **watch 它关心的资源（CR + 子资源），一旦发现"现状偏离期望"，运行 Reconcile 让它们重新对齐。**

用 controller-runtime（最主流的 Operator 框架，Kubebuilder/Operator SDK 都基于它）写一个 Controller 的骨架：

```go
type RayClusterReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

func (r *RayClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 读 CR
    var rc rayv1.RayCluster
    if err := r.Get(ctx, req.NamespacedName, &rc); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }
    // 2. 读子资源、算 diff、act（见 2.3）
    // 3. 写 status
    // 4. 决定是否重新入队
    return ctrl.Result{}, nil
}

func (r *RayClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&rayv1.RayCluster{}).                    // 主资源：RayCluster CR
        Owns(&appsv1.Deployment{}).                 // 子资源：它创建的 Deployment
        Owns(&corev1.Service{}).                    // 子资源：Service
        Complete(r)
}
```

**`For` 与 `Owns`**：

- `For(&RayCluster{})`：Controller 的主资源，watch 它的变化，每次变都触发 reconcile。
- `Owns(&Deployment{})`：Controller **拥有**的子资源（通过 owner reference 关联）。子资源变（Pod 重建、spec 改）也会触发对应 CR 的 reconcile——这是"自愈"的基础（Pod 挂了 → Deployment 变 → 触发 reconcile → Controller 发现少了副本 → 重建）。

## 2.3 Reconcile：level-triggered 的纯函数

Reconcile 是 Operator 的心脏。它的**契约**是：

> **给定一个"要调和哪个 CR"的请求（namespace/name），让该 CR 描述的实际状态趋近期望状态；返回"是否需要稍后重试"。**

一次 Reconcile 的标准流程（伪代码）：

```
Reconcile(req):
    1. rc = 读 RayCluster CR (req.namespacedName)
       若 not found → 返回 OK（CR 被删，可能要清理，见 finalizer）
    2. 期望 = rc.spec（1 head + 4 worker + image=2.9.0）
    3. 现状 = 读所有相关子资源（实际有几个 Deployment、几个 ready Pod）
    4. diff = 期望 vs 现状
    5. if diff != 0: act（create/update/delete 子资源）让现状 → 期望
    6. 更新 rc.status（ready=true/false, workerReady=N）
    7. if 尚未收敛 or 需要轮询: 返回 Result{RequeueAfter: 30s}
       else: 返回 Result{}（完成，等下一次事件）
```

Reconcile 有四个**铁律**，理解它们就理解了 Operator 的灵魂：

### 铁律 1：level-triggered（基于全量状态），不是 edge-triggered（基于事件）

Reconcile 不关心"发生了什么变化"（那是 edge），只关心"**现在**是什么状态、和期望差多少"（那是 level）。给它一个 CR 的名字，它从头读全量状态、算 diff、纠正。

- **为什么这重要**：如果中间漏掉了若干事件（网络抖动、Controller 重启），level-triggered 仍然能收敛——因为它每次都基于当前真实全量，不依赖"事件序列"。edge-triggered（脚本式）漏一个事件就永远错了。
- **类比**：恒温器是 level-triggered（"现在 18°，目标 22° → 加热"），不管你什么时候开窗；传统告警脚本常是 edge-triggered（"收到温度告警 → 跑一次"），漏告警就不处理。

### 铁律 2：幂等（多次执行结果一致）

Reconcile 必须幂等——同一个 CR 被调和 100 次，结果和调和 1 次一样。因为 K8s 会因为各种原因（事件、resync、退避重试）多次调用它。

- **实现**：act 之前先判断"现状是否已经满足"，满足就跳过。例如创建 Deployment 前先 `Get`，已存在就只更新需要改的字段；不要无条件 `Create`。
- **反模式**：`Reconcile 里每次都 Create 一个 Pod` → 会创建无数 Pod。正确：`Get 现有 Pod 数，少了才 Create`。

### 铁律 3：不能阻塞（单次 reconcile 必须快速返回）

Reconcile 是在一个 goroutine 里串行处理 workqueue 里的请求（默认）。如果一次 reconcile 阻塞（等网络、sleep、跑长任务），会卡住整个 Controller 的处理。

- **长任务怎么办**：不要在 reconcile 里 `time.Sleep(60s)` 等模型加载。而是返回 `Result{RequeueAfter: 30s}`，让 Controller 30 秒后再调和一次——这期间 Controller 能处理其他 CR。
- **重活外包**：真正耗时的工作（训练、推理）由 Operator 创建的 Pod 去做，Operator 只负责"编排"，不亲自下场。

### 铁律 4：乐观返回（不保证一次收敛）

一次 Reconcile 不必把所有事做完。可以"做一步、返回、稍后继续"。例如创建 Deployment 后立即返回 `RequeueAfter: 10s`，下一次 reconcile 再检查 Pod 是否 ready。**最终一致**是目标，不是"立刻一致"。

> **这四条铁律和 K8s 内置 Controller 完全一样**（见 [K8s 第 4 章](../kubernetes/04-runtime-workflow)）。再次印证：Operator 就是用户态的 K8s Controller。

## 2.4 Finalizer：删除前的安全钩子

直接删一个有外部依赖的 CR 会出问题：RayCluster 删了，但 Ray 集群在云厂商负载均衡器上的资源没清、S3 上的 checkpoint 没归档。**Finalizer** 解决"删除前必须做清理"。

机制：CR 的 `metadata.finalizers` 列表里有名字时，apiserver **不会真正删除**它（只设 `deletionTimestamp`）。Controller 在 reconcile 时发现 `deletionTimestamp != nil`，执行清理逻辑，完成后**把 finalizer 从列表移除**——最后一个 finalizer 移除时，apiserver 才真正删除 CR。

```go
func (r *RayClusterReconciler) Reconcile(...) {
    // ...
    if !rc.ObjectMeta.DeletionTimestamp.IsZero() {
        // 正在删除 → 跑清理（归档 checkpoint、注销 LB、通知下游）
        if err := r.cleanup(ctx, &rc); err != nil {
            return ctrl.Result{Requeue: true}, err   // 清理失败，稍后重试
        }
        // 清理成功 → 移除 finalizer
        controllerutil.RemoveFinalizer(&rc, "ray.io/finalizer")
        if err := r.Update(ctx, &rc); err != nil {
            return ctrl.Result{}, err
        }
        return ctrl.Result{}, nil
    }
    // 正常 reconcile（确保 finalizer 存在）
    if !controllerutil.ContainsFinalizer(&rc, "ray.io/finalizer") {
        controllerutil.AddFinalizer(&rc, "ray.io/finalizer")
        _ = r.Update(ctx, &rc)
        return ctrl.Result{Requeue: true}, nil
    }
    // ... 正常调和
}
```

**坑**：Finalizer 写错（清理逻辑永远失败）会导致 CR **永远删不掉**（卡在 `Terminating`）。生产事故的常见来源（见第 9、10 章）。解法：清理逻辑必须可重试、有超时、可人工强制移除 finalizer。

## 2.5 Owner Reference：级联垃圾回收

Operator 创建的子资源（head Deployment、worker StatefulSet、Service）应该和 CR **同生共死**——CR 删了，子资源自动清理。这靠 **Owner Reference** 实现：

```go
// Controller 创建子资源时，设置 owner 为 CR
deployment := &appsv1.Deployment{...}
ctrl.SetControllerReference(&rc, deployment, r.Scheme)  // 设置 ownerReference
r.Create(ctx, deployment)
```

设置后，子资源的 `metadata.ownerReferences` 指向 CR。K8s 的垃圾回收控制器检测到 owner 被删，自动删子资源（级联）。这让"删除一个 CR = 清理整个应用"成为可能。

> **和 Finalizer 的分工**：Owner Reference 处理"K8s 内部子资源的级联删除"；Finalizer 处理"K8s 外部资源（S3、DNS、云 LB）的清理"。两者协作完成完整删除语义。

## 2.6 Status：报告实际状态

`status` 是 Controller 写回 CR 的"实际状态报告"，是用户和监控系统判断"应用到底好了没"的唯一来源。设计原则：

- **只由 Controller 写**：用户不该手改 status（apiserver 的 `/status` 子资源 + RBAC 强制）。
- **结构化 conditions**：用 `status.conditions`（一组 `{type, status, reason, message, lastTransitionTime}`）描述多个维度的状态（`Ready`、`Progressing`、`Available`），比单个 bool 富信息。
- **`observedGeneration`**：记录 Controller 已经处理到 CR 的哪一版 `generation`。`status.observedGeneration == metadata.generation` 说明 Controller 已经看到并处理了最新 spec——这是判断"spec 改了但 Controller 还没反应"的关键（见第 9 章）。

```yaml
status:
  observedGeneration: 3        # 已处理到第 3 版 spec
  ready: true
  workerReady: 4
  conditions:
    - type: Ready
      status: "True"
      reason: AllWorkersReady
      lastTransitionTime: "2026-07-04T10:00:00Z"
    - type: Progressing
      status: "False"
```

## 2.7 Webhook：准入控制（validating / mutating / conversion）

Webhook 是 apiserver 在**写入 etcd 之前**调用的外部回调，给 Operator 一次"拦截 + 校验/修改"的机会。三类：

| 类型 | 时机 | 用途 | 示例 |
|---|---|---|---|
| **mutating**（准入修改） | 创建/更新前，可改对象 | 设默认值、注入 sidecar、规范化字段 | 给 RayCluster 注入默认 `serviceUnhealthySecondThreshold` |
| **validating**（准入校验） | 创建/更新前，只读校验 | 拒绝非法配置（比 CRD schema 更复杂的业务规则） | 拒绝 `workerReplicas > GPU 配额`、拒绝改不可变字段 |
| **conversion**（版本转换） | 多版本 CRD 读写时 | 把 `v1alpha1` ↔ `v1` 互转 | CRD 升级时让旧客户端继续用 v1alpha1 |

**与 CRD schema 的分工**：CRD schema 校验"类型/格式"（字段是 int、字符串匹配正则）；webhook 校验"业务语义"（worker 数不能超配额、primary 不可降级）。两者互补。

> **生产要点**：Webhook 是**控制平面关键路径**——它挂了，所有相关 CR 的创建/更新都会卡住（甚至整个 namespace）。必须高可用部署 + 有超时 + 失败时 fail-open 还是 fail-close 要想清楚（见第 8 章）。

## 2.8 Operator 的"控制平面"心智模型

把前 7 节组合起来，一个生产 Operator 的完整心智模型：

```
   用户                  apiserver (etcd)              Controller 进程
   ────                  ──────────────                ──────────────
   kubectl apply CR ──►  存储 CR ──watch────────────►  Informer/Cache（本地缓存）
                                                         │ 事件入 Workqueue
                                                         ▼
                                                      Reconcile(req)
                                                         │ 1. 读 CR（从 cache）
                                                         │ 2. 读子资源（从 cache）
                                                         │ 3. 算 diff
                                                         │ 4. act: Create/Update/Delete
                                                         │    ──────►  apiserver ──► etcd
                                                         │ 5. 写 status ──►  apiserver
                                                         │ 6. 若未收敛: RequeueAfter
                                                         ▼
                                                      （循环）
                          ▲                              │
   kubectl get status ◄──┴── status 子资源 ◄─────────────┘
```

**三条信息流**：

1. **意图流**（用户 → etcd → Controller）：用户写 spec，Controller 通过 watch 感知。
2. **调和流**（Controller → apiserver → 集群）：Controller act，创建/修改子资源。
3. **状态流**（Controller → etcd → 用户）：Controller 写 status，用户/监控读取。

这三条流构成了一个**闭环**：意图驱动调和，调和改变现状，现状反馈为状态，状态暴露给观测——这正是控制论里的负反馈系统，也是 K8s 声明式 API 的数学本质。

## 本章小结

- **CRD + CR**：CRD 定义资源类型（类），CR 是实例（对象）；CRD 用 OpenAPI v3 校验 spec，`spec`（期望）/`status`（实际）分离是核心约定。
- **Controller**：永远在线的 watch 进程，`For` 主资源 + `Owns` 子资源；通过 owner reference 把子资源和 CR 绑定。
- **Reconcile**：level-triggered、幂等、不阻塞、乐观返回的纯函数——读现状 → 算 diff → act → 写 status。四条铁律和 K8s 内置 Controller 完全一致。
- **Finalizer**：删除前的安全钩子，处理 K8s 外部资源清理；写错会卡住删除。
- **Owner Reference**：级联垃圾回收，CR 删了子资源自动清。
- **Status**：Controller 写的实际状态报告，`conditions` + `observedGeneration` 是关键设计。
- **Webhook**：准入控制（mutating/validating/conversion），校验业务语义、设默认值、做版本转换。
- **心智模型**：意图流 → 调和流 → 状态流构成闭环负反馈系统——这是 K8s 声明式 API 的本质。

**参考来源**

- [Kubernetes — CustomResourceDefinition](https://kubernetes.io/zh-cn/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
- [controller-runtime — Reconcile loop](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg/reconcile)
- [Kubebuilder Book](https://book.kubebuilder.io/) —— CRD/Controller/Reconcile 的权威教程。
- 本手册 [Kubernetes 第 4 章](../kubernetes/04-runtime-workflow)（控制循环同构性）、[Helm 第 2 章](../helm/02-core-ideas)（spec/status 约定对比）。
