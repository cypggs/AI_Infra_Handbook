# 5. 核心模块：Operator 的十大组件

> 一句话理解：把前几章散落的零件摆到一张表上——本章逐一讲透 Operator 的十个核心模块（CRD/schema、Controller、Reconciler、Workqueue、Informer/Cache、Webhook、Finalizer、Status、Leader Election、RBAC/Metrics），每个模块讲"做什么、怎么做、踩什么坑"，最后给一张全景对照图，让你在写或读 Operator 时能立刻定位"这个行为归哪个模块管"。

## 5.1 模块全景对照

| # | 模块 | 职责 | 实现位置 | 易踩的坑 |
|---|---|---|---|---|
| 1 | CRD + schema | 定义资源类型、校验 spec | apiserver + OpenAPI v3 | schema 太松导致脏数据；多版本转换缺 webhook |
| 2 | Controller | 串起 Source→Queue→Reconciler | controller-runtime | Owns 漏注册子资源 → 自愈失效 |
| 3 | Reconciler | 业务逻辑（读/diff/act/status） | 开发者写的代码 | 非幂等、阻塞、依赖事件序列 |
| 4 | Workqueue | 去重 + 退避重试 | controller-runtime | 误用 `Requeue:true` 造成风暴 |
| 5 | Informer/Cache | 本地缓存 + watch | controller-runtime Cache | 读写不一致（Cache 滞后）|
| 6 | Webhook | 准入校验/修改/转换 | Operator 进程的 :9443 | webhook 挂了卡住整个集群写入 |
| 7 | Finalizer | 删除前清理外部资源 | Reconciler 删除分支 | 清理逻辑永远失败 → CR 卡死 |
| 8 | Status | 报告实际状态 | Reconciler 写 /status | observedGeneration 不更新；condition 设计粗糙 |
| 9 | Leader Election | 多副本单干活 | Lease 资源 | 没开 → 多副本竞争 |
| 10 | RBAC / Metrics | 权限 + 可观测 | ClusterRole + /metrics | 权限过大；无 reconcile 错误告警 |

下面逐个展开。

## 5.2 CRD + schema：资源的"宪法"

第 2 章给过骨架，这里讲**设计要点**：

- **schema 要严**：每个 spec 字段都加 type + 约束（minimum/maximum/enum/pattern）。AI 场景尤其：`replicas` 加 `minimum: 1`、`gpuPerReplica` 加 `enum: [1,2,4,8]`、`modelName` 加 `pattern`。schema 松 = 脏数据进 etcd = Controller 崩。
- **`x-kubernetes-list-type: map`**：list 字段若需要"按 key 增量合并"（不被整体替换），加这个注解，配合 server-side apply 实现 Helm 三方合并类似的语义。
- **`preserveUnknownFields: false`**（v1 默认）：未知字段被 prune（删），不进 etcd。防止 CRD 升级后旧字段残留。
- **多版本 + conversion**：声明 `v1alpha1`/`v1beta1`/`v1`，配 conversion webhook 互转（见第 8 章）。生产 CRD 必须考虑版本演进。
- **printer columns**：`additionalPrinterColumns` 让 `kubectl get raycluster` 直接显示关键列（如 READY/AGE），不靠 `-o yaml`。

```yaml
versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required: [image, replicas]
            properties:
              image:    { type: string, pattern: '^[\w./-]+:[\w.-]+$' }
              replicas: { type: integer, minimum: 1, maximum: 100 }
              gpuPerReplica: { type: integer, enum: [1, 2, 4, 8] }
    additionalPrinterColumns:
      - name: Replicas
        type: integer
        jsonPath: .spec.replicas
      - name: Ready
        type: string
        jsonPath: .status.ready
      - name: Age
        type: date
        jsonPath: .metadata.creationTimestamp
```

## 5.3 Controller：流水线的组装者

Controller 不写业务逻辑，它**组装流水线**（见第 3.5 节）。`SetupWithManager` 是组装点，最常踩的坑是 **Owns 漏注册**：

```go
// ❌ 漏 Owns ConfigMap → ConfigMap 被人改了，Controller 不知道，不自愈
return ctrl.NewControllerManagedBy(mgr).
    For(&rayv1.RayCluster{}).
    Owns(&appsv1.Deployment{}).
    Complete(r)

// ✅ Controller 创建的所有子资源都要 Owns
return ctrl.NewControllerManagedBy(mgr).
    For(&rayv1.RayCluster{}).
    Owns(&appsv1.Deployment{}).
    Owns(&corev1.Service{}).
    Owns(&corev1.ConfigMap{}).
    Owns(&corev1.ServiceAccount{}).
    Complete(r)
```

漏 Owns 的后果：子资源被人改/删，Controller **收不到事件**，不会 reconcile 纠偏——自愈失效。生产事故常见来源。

**跨资源 watch**（watch 不拥有的资源）：用 `Watches(src, handler)`，配 `EnqueueRequestsFromMapFunc` 把外部事件映射到 CR。例：节点变化 → 重新调和所有调度受影响的 CR。

## 5.4 Reconciler：业务逻辑的唯一战场

开发者只写 `Reconcile`。第 4 章详述了流程，这里强调**代码组织最佳实践**：

- **单一职责**：一个 Reconciler 管一种 CR。复杂应用拆多个 CRD（如 Ray 拆 RayCluster/RayService/RayJob），每个一个 Reconciler。
- **状态机思维**：把应用生命周期建模成状态机（Creating→Scaling→Ready→Upgrading→Deleting），reconcile 根据 `status.phase` 走不同分支，每步只做最小动作 + 推进状态。
- **helper 函数**：把"创建 Deployment""等 Pod ready""算健康度"抽成函数，Reconcile 主干保持清晰。
- **日志 + 事件**：关键节点 `r.Recorder.Eventf(&rc, "Normal", "Scaled", "replicas %d→%d", old, new)`，让 `kubectl describe` 能看到 Operator 在干什么——可观测性基础。

```go
func (r *RayClusterReconciler) Reconcile(ctx, req) (ctrl.Result, error) {
    rc, err := r.getCluster(ctx, req.NamespacedName)
    if err != nil || rc == nil { return ctrl.Result{}, err }

    switch rc.Status.Phase {
    case "", PhaseCreating:
        return r.reconcileCreating(ctx, rc)
    case PhaseScaling:
        return r.reconcileScaling(ctx, rc)
    case PhaseReady:
        return r.reconcileReady(ctx, rc)        // 稳态，可能 RequeueAfter 周期检查
    case PhaseUpgrading:
        return r.reconcileUpgrading(ctx, rc)
    }
    return ctrl.Result{}, nil
}
```

## 5.5 Workqueue：抗风暴的缓冲

Workqueue 的三个特性（去重、延迟、退避）第 3 章讲过。这里讲**怎么用对 Requeue**：

| 场景 | 该返回 | 理由 |
|---|---|---|
| 已收敛，无需轮询 | `Result{}, nil` | 等外部事件触发即可 |
| 等 Pod ready / 模型加载 | `RequeueAfter: 30s` | 周期检查，不阻塞 |
| 证书续期 / 定期备份检查 | `RequeueAfter: 1h` | 长周期轮询 |
| act 失败（apiserver 限流） | `error` | 让框架指数退避 |
| 业务上需要立即再看一次 | `Requeue: true` | **少用**，易自我风暴 |

**反模式**：`return Result{Requeue: true}, nil` 在每次 reconcile 末尾 → 无条件立即重排 → Controller 100% CPU、队列永远满。几乎总是错，应改用 `RequeueAfter` 或干脆 `Result{}`。

## 5.6 Informer/Cache：读写分离的代价

Cache 是性能利器，但有**滞后代价**：

- **读滞后**：Cache 比 apiserver 慢几百毫秒到几秒（watch 传播延迟）。绝大多数场景可接受（level-triggered 容忍），但"刚 Create 完立即 Get"可能 Get 不到——这时要么用 `client.NewDryRunClient`、要么依赖返回的对象。
- **写后读**：`r.Create(ctx, d)` 后立即 `r.Get(ctx, ..., d)` 可能拿不到（Cache 没更新）。正确做法：Create 返回的对象本身就含 apiserver 赋的 field（uid/resourceVersion），直接用。
- **List 限制**：`r.List` 从 Cache 拿，但若 Cache 还没同步完（启动初期），可能拿空。Manager 的 readiness 检查保证"Cache 同步完才标记 ready"，避免这个问题。
- **强一致读**：极少数需要最新数据的场景，用 `client.NewAPIReader`（绕过 Cache 直查 apiserver）——但贵，少用。

## 5.7 Webhook：准入控制的双刃剑

第 2.7 节介绍了三类 webhook。生产要点：

- **高可用**：webhook 是控制平面关键路径，挂了相关 CR 全部写不进。至少 2 副本 + 反亲和。
- **超时**：apiserver 调 webhook 默认 10s 超时。webhook 实现必须快（< 1s），不调外部慢服务。
- **fail-open vs fail-close**：webhook 配置 `failurePolicy`——`Ignore`（webhook 挂了放行）还是 `Fail`（挂了拒绝）。生产通常对 mutating 用 Ignore（避免卡死）、对关键 validating 用 Fail（宁可拒绝也别放过非法配置）。
- **namespace selector**：用 `namespaceSelector` 限制 webhook 只作用于特定 namespace（如带 `operator-enabled=true` 标签的），避免误伤系统命名空间（webhook 配错把 kube-system 卡死是经典事故）。
- **证书**：apiserver 用 webhook server 的 CA 证书做 mTLS。证书过期 → webhook 全部失败 → 集群写入瘫痪。用 cert-manager 自动轮换。

## 5.8 Finalizer：删除前的安全网

第 2.4、4.9 节讲过机制。设计要点：

- **清理逻辑必须幂等 + 可重试**：外部资源（S3/DNS/LB）的清理可能因网络临时失败，必须能重试到成功。
- **超时**：给清理一个上限（如 5 分钟），超时仍未成功就放弃并写 event 告警，让人介入——避免无限卡。
- **命名约定**：finalizer 名用 `<group>/<purpose>`（如 `ray.io/cleanup-loadbalancer`），一个 Operator 可有多个 finalizer 各管一类外部资源。
- **强制移除逃生口**：文档里写清楚"CR 卡 Terminating 怎么救"（patch 清空 finalizers），但要警告这会跳过清理。

## 5.9 Status：对外界的承诺

status 是用户和监控系统判断应用健康的唯一窗口。设计要点：

- **observedGeneration**：每次写 status 必更新它 = 当前 spec 的 generation。外部可据此判断"spec 改了 Controller 是否已响应"。
- **conditions**：用标准 `[]Condition`（type/status/reason/message/lastTransitionTime）描述多维度状态。遵循 K8s 约定（`Ready`/`Available`/`Progressing`/`Degraded`），让工具（kubectl、dashboard）能通用展示。
- **不要把敏感信息放 status**：status 进 etcd，可能被 list 出来。密码/token 走 Secret。
- **status 体积**：别把大对象（完整配置、日志）塞 status（etcd 单对象有 1.5MB 限制）。大对象放 ConfigMap/对象存储，status 只放引用。

```yaml
status:
  observedGeneration: 4
  phase: Ready
  readyReplicas: 4
  conditions:
    - {type: Ready,        status: "True",  reason: AllReady,    lastTransitionTime: "..."}
    - {type: Progressing,  status: "False", reason: Stable,      lastTransitionTime: "..."}
    - {type: Degraded,     status: "False", reason: NoErrors,    lastTransitionTime: "..."}
```

## 5.10 Leader Election：多副本的协调

第 3.6 节讲过机制。生产配置：

- **必须开**（生产）：`LeaderElection: true`，否则多副本竞争会造成重复操作 + status 互相覆盖。
- **Lease 参数**：`leaseDuration`（租期，默认 15s）、`renewDeadline`（续约间隔，默认 10s）、`retryPeriod`（重试间隔，默认 2s）。调优原则：leaseDuration > renewDeadline > retryPeriod，且 leaseDuration 要明显大于网络抖动预期。
- **Leader 切换间隙**：旧 leader 崩溃到新 leader 接管有间隙（约 leaseDuration），这期间不 reconcile——业务要能容忍短暂无调和（level-triggered 保证接管后立刻收敛）。
- **不同 Operator 不同 Lease 名**：同集群多 Operator 各用不同 `LeaderElectionID`，避免抢同一个锁。

## 5.11 RBAC + Metrics：权限与可观测

**RBAC**（Controller 用 kubebuilder 注解生成 ClusterRole）：

```go
//+kubebuilder:rbac:groups=ray.io,resources=rayclusters,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=ray.io,resources=rayclusters/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=apps,resources=deployments,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=services;configmaps,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=events,verbs=create;patch
```

- **最小权限**：只授予 Controller 真正需要的资源 + 动词。`cluster-admin` 是安全审查红线。
- **status 子资源单独授权**：`rayclusters/status` 单列，体现 spec/status 分离。
- **events**：写 Event 需要 `create;patch`，让 `kubectl describe` 显示 Operator 行为。

**Metrics**（controller-runtime 自动暴露，`:8080/metrics`）：

| 指标 | 含义 | 告警建议 |
|---|---|---|
| `controller_runtime_reconcile_total` | reconcile 次数（按 controller/result 标签） | 速率突变 |
| `controller_runtime_reconcile_errors_total` | reconcile 失败次数 | > 0 持续 → 告警 |
| `controller_runtime_reconcile_time_seconds` | reconcile 耗时分布 | p99 > 1s → 调查阻塞 |
| `controller_runtime_max_concurrent_reconciles` | 并发度 | — |
| `workqueue_depth` | 队列深度 | 持续高 → 处理不过来 |

> **告警铁律**：`reconcile_errors_total` 持续 > 0 必须告警——它意味着 Controller 在反复失败重试，往往预示真实故障（CR 配置错、依赖不可达、代码 bug）。这是 Operator 健康的第一指标。

## 5.12 全景对照图（再放一次，加深印象）

```
   apiserver/etcd
       ▲│ watch(List+Watch)
       │▼
   ┌──────────── Manager ────────────┐
   │  Cache (Informer) ──► 本地缓存    │  ← 模块 5
   │  Client (读Cache/写apiserver)    │  ← 模块 5（读写分离）
   │  Leader Election (Lease)         │  ← 模块 9
   │  Webhook Server (:9443)          │  ← 模块 6
   │  Metrics (:8080) / Health (:8081)│  ← 模块 10
   │  ┌── Controller ──┐              │
   │  │ Source(For/Owns)│             │  ← 模块 2（含 1 CRD）
   │  │   ↓             │             │
   │  │ Workqueue(去重) │             │  ← 模块 4
   │  │   ↓ pop         │             │
   │  │ Reconciler ─────┼─► act       │  ← 模块 3
   │  │   ├─ finalizer  │             │  ← 模块 7
   │  │   └─ status ────┼─► /status   │  ← 模块 8
   │  └─────────────────┘             │
   │  RBAC (ClusterRole)              │  ← 模块 10
   └──────────────────────────────────┘
```

## 本章小结

- **十大模块**各司其职：CRD（定义）、Controller（组装）、Reconciler（逻辑）、Workqueue（缓冲）、Cache（缓存）、Webhook（准入）、Finalizer（清理）、Status（报告）、Leader Election（协调）、RBAC/Metrics（权限/观测）。
- **最易踩的坑**：Owns 漏注册（自愈失效）、Reconcile 非幂等/阻塞、Webhook 挂卡集群、Finalizer 永续失败卡删除、status 不更新 observedGeneration、Leader Election 没开、RBAC 过大、无 reconcile 错误告警。
- **设计哲学**：CRD schema 要严、Reconciler 要状态机化、Workqueue 用 RequeueAfter 不用 Requeue、Cache 接受滞后、Webhook 必须 HA + 证书自动轮换、Finalizer 必须可重试、Status 用 conditions + observedGeneration、Leader Election 生产必开、RBAC 最小化、metrics 告警盯住 reconcile_errors。

**参考来源**

- [Kubebuilder Book](https://book.kubebuilder.io/) —— 各模块的权威实现指南。
- [controller-runtime API](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg)
- [Kubernetes — API Conventions（spec/status/conditions）](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- [cert-manager webhook 证书](https://cert-manager.io/docs/concepts/ca-injector/)
- 本手册第 2、3、4 章（机制基础）。
