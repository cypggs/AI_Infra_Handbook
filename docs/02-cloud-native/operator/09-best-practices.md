# 9. 最佳实践与反模式

> 一句话理解：写对 Operator 不难，写"好"的 Operator 靠的是避开十几个经典反模式。本章把生产里反复出现的正确做法和踩坑提炼成可对照的清单——Reconcile 设计、状态机、缓存与并发、删除与 finalizer、CRD 设计、可观测、测试——每条都给"反模式 → 正解"。

## 9.1 Reconcile 设计：状态机 + 子 reconciler

**反模式：一个巨型 Reconcile 函数**——500 行、if/else 嵌套、混杂创建/等待/状态推进。

**正解**：

- **状态机化**：用 `status.phase` 把生命周期建模成有限状态（Creating→Scaling→Ready→Upgrading→Failed），Reconcile 根据 phase 分发到子方法，每步只做最小动作 + 推进状态。
- **子 reconciler 拆分**：每个子资源（Deployment/Service/ConfigMap）一个 `reconcile*` 函数，各自幂等返回"是否修改"。主干只编排。
- **先算 desired 再 diff**：先把期望状态算成内存对象，再逐字段比现状——幂等的工程保障。

```go
switch rc.Status.Phase {
case "", PhaseCreating:  return r.reconcileCreating(ctx, rc)
case PhaseReady:         return r.reconcileReady(ctx, rc)    // 稳态 + RequeueAfter 周期检查
case PhaseUpgrading:     return r.reconcileUpgrading(ctx, rc)
}
```

## 9.2 幂等：先查再改，Patch 优于 Update

**反模式**：

- 无条件 `Create` → 重复 reconcile 创建无数资源。
- `Update` 全量覆盖 → 冲掉别人（或别的 Controller）改的字段。

**正解**：

- **先 Get 判断存在性**：存在则 Patch 差异，不存在才 Create。
- **Patch（基于 diff）优于 Update（全量）**：`client.MergeFrom(base).Patch(...)` 只改变化的字段，不冲突。
- **状态没变不写**：`if !reflect.DeepEqual(old, new)` 守卫，减少 apiserver 写入和事件噪声。

## 9.3 不阻塞：RequeueAfter 而非 sleep

**反模式**：Reconcile 里 `time.Sleep(60s)` 等模型加载 → 卡住 worker，整个 Controller 停摆。

**正解**：

- **长等待用 `RequeueAfter`**：返回 `{RequeueAfter: 30s}`，Controller 30s 后再调和，期间处理其他 CR。
- **重活外包给 Pod**：训练/推理由 Operator 创建的 Pod 做，Operator 只编排，不亲自下场。
- **外部调用加超时**：调云 API/对象存储必须带 context 超时，避免卡死。

## 9.4 Owns 与 owner reference：自愈的命脉

**反模式**：Reconciler 创建子资源时**忘了 `SetControllerReference`**，或 Controller **漏 `Owns` 注册**——子资源被人改/删，Operator 收不到事件，自愈失效。

**正解**：

- 每个创建的子资源都 `ctrl.SetControllerReference(owner, child, scheme)`。
- Controller 的 `SetupWithManager` 把所有拥有的子资源都 `Owns(...)`。
- 跨资源 watch 用 `Watches` + `EnqueueRequestsFromMapFunc` 把外部事件映射到 CR。

> 这是生产事故最常见来源之一（见第 5.3、6.5 节）。漏一个 Owns，对应子资源的漂移就无人纠正。

## 9.5 finalizer：可重试 + 有超时 + 有逃生口

**反模式**：

- 清理逻辑不可重试（外部资源暂时不可达 → 永远失败）→ CR 卡 Terminating。
- 清理成功但忘了移除 finalizer → CR 删不掉。
- 没有逃生口 → 线上事故时运维只能 etcd 手术。

**正解**：

- 清理逻辑**幂等 + 可重试**（网络临时失败能重试到成功）。
- 给清理一个**超时上限**（如 5 分钟），超时写 Event 告警让人介入。
- finalizer 命名 `<group>/<purpose>`，一个 Operator 可多个 finalizer 各管一类外部资源。
- 文档写明**强制移除逃生口**：`kubectl patch <cr> -p '{"metadata":{"finalizers":[]}}'`，并警告"会跳过清理"。

## 9.6 status：observedGeneration + 标准 conditions

**反模式**：

- 不更新 `observedGeneration` → 外界无法判断"spec 改了 Controller 是否响应"。
- status 只有一个 bool → 信息太少，上层编排瞎猜。
- 把密码/大对象塞 status → 安全风险 + etcd 1.5MB 限制。

**正解**：

- 每次写 status 设 `observedGeneration = metadata.generation`。
- 用标准 `conditions`（Ready/Progressing/Degraded/Available），每个含 type/status/reason/message/lastTransitionTime。
- 敏感信息走 Secret，大对象走 ConfigMap/对象存储，status 只放引用和摘要。

## 9.7 CRD 设计：schema 严、版本演进、printer columns

**反模式**：

- schema 太松（字段无 type/约束）→ 脏数据进 etcd → Controller 崩。
- 直接删/改字段 → 存量 CR 校验失败。
- 没配 printer columns → `kubectl get` 啥也看不到。

**正解**：

- 每个 spec 字段加 type + 约束（minimum/maximum/enum/pattern）。AI 场景：`replicas` 加 `minimum:1`、`gpuPerReplica` 加 `enum:[1,2,4,8]`。
- 字段废弃先 `deprecated:true`，保留一两版再删；版本演进走 conversion webhook。
- 配 `additionalPrinterColumns` 让 `kubectl get` 直接显示 READY/AGE。
- `preserveUnknownFields: false`（v1 默认）防旧字段残留。

## 9.8 缓存与并发：接受滞后，乐观重试

**反模式**：

- 依赖"写后立即读 Cache" → Cache 滞后，读到旧值或 NotFound。
- 用阻塞锁协调并发 → 死锁风险。

**正解**：

- **接受 Cache 最终一致**：level-triggered 容忍滞后；Create 返回的对象本身就含 apiserver 赋的字段，直接用。
- **写靠 resourceVersion 乐观锁**：Conflict 由 controller-runtime 自动退避重试，不要自己加锁。
- **强一致读用 APIReader**：极少数需要最新数据的场景用 `client.NewAPIReader`（绕过 Cache），但贵，少用。

## 9.9 可观测：盯 reconcile_errors

**反模式**：只暴露 metrics 不告警；或告警盯错指标（如只看 Pod CPU）。

**正解**：

- **第一告警指标**：`controller_runtime_reconcile_errors_total` 持续 > 0 → 立即告警。
- 关键节点写 Event（Scaled/Upgraded/Failed），让 `kubectl describe` 可读。
- status.conditions 让上层（dashboard/HPA/告警）有标准数据源。
- 监控 `workqueue_depth`（持续高 = 超载）和 reconcile p99 时长（>1s = 阻塞）。

## 9.10 测试：envtest + 三层

**反模式**：只在真集群手测，或完全不测 Reconcile。

**正解**：

- **envtest**（controller-runtime 提供）：起真实 etcd + apiserver（无 kubelet），跑真 CRD/Reconcile，快且隔离——单元测试 Reconcile 的标准工具。
- **三层测试**：单元（纯函数/helper）→ envtest（Reconcile 端到端）→ e2e（kind 集群，含 Operator 部署 + 升级）。
- **测幂等**：同一个 CR 连续 reconcile N 次，断言子资源数量不变。
- **测升级**：旧版 CR + 新版 Operator，断言向后兼容。
- **测删除**：有外部依赖的 CR 删除，断言 finalizer 清理 + 级联。

## 9.11 选型：什么时候**不**该写 Operator

Operator 不是银弹。写之前先问：

| 需求 | 该用什么 |
|---|---|
| 装一次 + 偶尔升级，参数多 | **Helm**（见 [Helm 第 1 章](../helm/01-background)） |
| 有头有尾的一次性流水线（DAG） | **Argo Workflow / Tekton** |
| 定时/一次性跑任务 | **Job/CronJob** |
| 长期运行 + 自动纠偏 + 多资源协同 + 领域逻辑 | **Operator** |

**判定法则**：只有"需要持续自愈 + 领域知识 + 多资源协同"三者俱全，才值得写 Operator。否则 Helm/Job/Workflow 更简单可靠。很多"看起来需要 Operator"的需求，其实 Helm + readiness probe 就够了。

## 9.12 速查：反模式 → 正解对照表

| 反模式 | 后果 | 正解 |
|---|---|---|
| 巨型 Reconcile | 难维护、易 bug | 状态机 + 子 reconciler |
| 无条件 Create | 重复创建 | 先 Get 再 Patch/Create |
| Update 全量覆盖 | 冲掉别人字段 | Patch（MergeFrom） |
| Reconcile 里 sleep | 卡死 worker | RequeueAfter |
| 漏 Owns/owner | 自愈失效 | 子资源都设 owner + Owns |
| finalizer 不可重试 | CR 卡 Terminating | 可重试 + 超时 + 逃生口 |
| 不更新 observedGen | 看不出是否响应 | 每次写 status 设 observedGen |
| schema 太松 | 脏数据崩溃 | 每字段加约束 |
| 写后立即读 Cache | 读到旧值 | 用 Create 返回值 / APIReader |
| 只看 CPU 不看 errors | 漏真实故障 | 告警 reconcile_errors |
| 需求简单却写 Operator | 过度工程 | Helm/Job/Workflow |

## 本章小结

- **Reconcile**：状态机化 + 子 reconciler 拆分 + 先算 desired 再 diff；幂等（先查再改、Patch 优于 Update）；不阻塞（RequeueAfter）。
- **自愈命脉**：每个子资源设 owner reference + Owns 注册；漏了就收不到事件。
- **删除**：finalizer 清理必须可重试 + 有超时 + 有强制移除逃生口。
- **status**：observedGeneration 必更新 + 标准 conditions + 无敏感/大对象。
- **CRD**：schema 严 + 版本演进 + printer columns。
- **并发**：接受 Cache 滞后，靠 resourceVersion 乐观锁 + Conflict 重试，别自己加锁。
- **可观测/测试**：盯 reconcile_errors；envtest + 三层测试。
- **选型**：只有"持续自愈 + 领域知识 + 多资源协同"三者俱全才写 Operator。

**参考来源**

- [Kubebuilder Book — Best Practices](https://book.kubebuilder.io/)
- [controller-runtime — envtest](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg/envtest)
- [Kubernetes API Conventions（conditions/observedGeneration）](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- [Red Hat — Kubernetes Patterns (Operator pattern)](https://www.redhat.com/en/resources/oreilly-kubernetes-patterns-cloud-native-apps)
- 本手册 [Helm 第 9 章](../helm/09-best-practices)（对照选型）、第 5、6 章（机制/源码）。
