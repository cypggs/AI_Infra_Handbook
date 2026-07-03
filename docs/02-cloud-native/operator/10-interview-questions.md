# 10. 面试题精选

> 一句话理解：本章按初/中/高三级整理 24 道 Operator 高频面试题，覆盖机制、工程、生产——每题给"考点 + 参考答案要点"，帮你把前九章的知识点串成能讲清楚的表达。

## 10.1 初级（概念与机制，8 题）

**Q1. 用一句话解释 Operator 模式。**

考点：CoreOS 定义的本质。答：Operator = CRD（自定义资源扩展 K8s API）+ 自定义 Controller（持续 watch + reconcile 的控制循环），把领域专家的运维知识编码成"永远在线、自动纠偏"的代码。它与 K8s 内置 Controller 机制同构，只是管领域对象而非通用 Pod 副本数。

**Q2. Operator 和 Helm 的区别？什么时候用哪个？**

考点：一次性安装 vs 持续管理。答：Helm 是模板渲染 + 一次性 apply，装完即走，不持续监控；Operator 是 CRD + 控制循环，持续自愈。要"装一次 + 参数多"用 Helm；要"长期运行 + 自动纠偏 + 领域逻辑"用 Operator。最常见组合：Helm 装 Operator，Operator 管业务。

**Q3. 什么是 Reconcile 的 level-triggered？为什么不用 edge-triggered？**

考点：状态 vs 事件。答：level-triggered 基于"当前全量状态"算 diff（恒温器模型）；edge-triggered 基于"发生了什么事件"（脚本模型）。level-triggered 在漏掉中间事件（网络抖动、Controller 重启）时仍能收敛，因为它每次读全量；edge-triggered 漏一个事件就永远错了。

**Q4. Reconcile 的四条铁律是什么？**

考点：契约。答：① level-triggered（读全量）；② 幂等（多次调和结果一致）；③ 不阻塞（单次快速返回，长等待用 RequeueAfter）；④ 乐观返回（不保证一次收敛，最终一致即可）。

**Q5. `For` 和 `Owns` 的区别？**

考点：Controller 装配。答：`For` 是主资源（watch CR 本身，事件映射到它自己）；`Owns` 是子资源（watch 它，事件通过 ownerReference 反查映射到 owner CR）。漏 `Owns` → 子资源变化收不到事件 → 自愈失效。

**Q6. spec 和 status 有什么区别？谁写？**

考点：声明式 API 约定。答：spec 是用户写的"期望状态"，status 是 Controller 写的"实际状态"。spec 变更 bump generation，status 不变。status 通过 `/status` 子资源单独写入（独立 resourceVersion），避免写 status 触发 spec 的 reconcile 死循环。

**Q7. 什么是 finalizer？解决了什么问题？**

考点：删除安全。答：finalizer 是 `metadata.finalizers` 列表里的名字；有 finalizer 的对象 delete 只设 deletionTimestamp 不真删，Controller 在 reconcile 时发现删除中就执行清理（外部资源），完成后移除 finalizer，最后一个移除时 apiserver 才真删。解决"删 CR 前必须清理 K8s 外部资源（S3/DNS/LB）"。

**Q8. Owner Reference 解决什么问题？**

考点：级联回收。答：让子资源和 CR 同生共死——CR 删了，K8s 垃圾回收控制器检测到 owner 被删，自动级联删子资源。和 finalizer 分工：owner reference 管 K8s 内部子资源级联，finalizer 管 K8s 外部资源清理。

## 10.2 中级（工程与实现，9 题）

**Q9. controller-runtime 的 Manager 和 Controller 各管什么？**

考点：架构分层。答：Manager 管进程生命周期——持有共享 Cache/Client、Leader Election、Metrics/Health/Webhook Server、管理所有 Controller 的启停。Controller 管单个 reconcile 循环——Source→EventHandler→Workqueue→Reconciler 流水线。一个 Manager 可挂多个 Controller。

**Q10. 为什么 Controller 读资源走 Cache 而不直查 apiserver？**

考点：Informer/Cache。答：① 快（本地内存）；② 不压 apiserver（频繁 reconcile 直查会打爆 apiserver）。代价是 Cache 有几秒滞后，但 level-triggered 容忍。写仍直通 apiserver。

**Q11. Workqueue 的去重为什么重要？**

考点：抗事件风暴。答：K8s 资源变化可能极快（一个 Deployment 短时间 spec 改 10 次），但 level-triggered 只需"调和到最新状态"一次。Workqueue 按 ns/name 去重，保证不管中间多少事件，最终只 reconcile 一次到最新——这是 level-triggered 扛住事件风暴的工程基础。

**Q12. Reconcile 返回值的四种语义？**

考点：Requeue。答：`Result{},nil`（完成等事件）；`RequeueAfter:Ns,nil`（N 秒后再调和，用于等 Pod ready/周期检查）；`Requeue:true,nil`（立即重排，少用）；任意+`error`（指数退避重试）。

**Q13. 什么是乐观并发？Controller 怎么用它？**

考点：resourceVersion。答：每个对象有 resourceVersion；update 带上"读到的"rv，若与 etcd 现存不一致 apiserver 返回 409 Conflict。Controller 读走 Cache（滞后）、写带 rv，冲突时 controller-runtime 自动退避重试——读后写的并发安全完全靠它，不用加锁。

**Q14. generation 和 observedGeneration 的区别？为什么重要？**

考点：版本追踪。答：generation 是 spec 每次变更 +1（status 不变）；observedGeneration 是 Controller 写进 status 的"我已处理到第 N 版"。`observedGeneration == generation` 说明 Controller 已响应最新 spec；不等说明"spec 改了 Controller 还没反应"——这是判断 Operator 是否跟上的关键。

**Q15. Leader Election 为什么必要？机制是什么？**

考点：多副本协调。答：多副本都 reconcile 会重复操作 + status 互相覆盖。Leader Election 用一个 Lease 资源做分布式锁，抢到的成为 leader 启动 Controller，其他待命；leader 心跳续约，崩溃则其他接管。和 K8s 内置 Controller Manager 机制一致。

**Q16. Webhook 的三类是什么？生产要注意什么？**

考点：准入控制。答：mutating（修改/设默认值）、validating（校验业务语义）、conversion（多版本 CRD 互转）。生产：webhook 是控制平面关键路径，挂了相关 CR 写不进——必须 ≥2 副本 + <1s 响应 + failurePolicy 明确 + namespaceSelector 限范围 + 证书自动轮换（过期会瘫痪集群写入）。

**Q17. 怎么测试一个 Operator？**

考点：测试策略。答：用 controller-runtime 的 envtest（起真实 etcd+apiserver 无 kubelet，跑真 CRD/Reconcile）做 Reconcile 单元测试；三层：单元（helper）→ envtest（端到端 reconcile）→ e2e（kind 集群含部署+升级）。重点测幂等（连续 reconcile 子资源数不变）和删除（finalizer 清理 + 级联）。

## 10.3 高级（生产与深度，7 题）

**Q18. 一个 CR 卡在 Terminating 删除不掉，怎么排查和救？**

考点：finalizer 故障。答：先 `kubectl describe` 看 finalizers 列表 + events，判断是哪个 finalizer 的清理逻辑失败（外部资源不可达/逻辑 bug）。若是清理永远失败且无法修，逃生口：`kubectl patch <cr> -p '{"metadata":{"finalizers":[]}}' --type=merge` 强制移除（警告：跳过清理，外部资源残留）。长期：清理逻辑必须可重试 + 有超时。

**Q19. Operator 创建的 Deployment 被人手动改了副本数，会发生什么？**

考点：漂移自愈。答：几秒内被 Operator 改回 spec 期望值——这是设计行为（level-triggered 纠偏）。因为 Deployment 是 Operator Owns 的子资源，它的变化触发 owner CR 的 reconcile，Reconciler 算出现状 ≠ 期望就 Patch 纠回。要改副本数应改 CR.spec，不是改子资源。

**Q20. 怎么设计一个支持金丝雀升级的推理 Operator？**

考点：AI 场景设计。答：CR spec 支持主版本 + canary 版本 + `canaryTrafficPercent`；Reconciler 维护两套 Deployment（stable + canary），Service 用权重或两 Service + 流量分流按比例导流；canary 的 readiness/指标达标后逐步提比例，全量后回收 stable。注意模型加载延迟——canary Pod ready 要等 `/health`（领域就绪）而非 TCP。

**Q21. CRD 从 v1beta1 演进到 v1，怎么无损迁移？**

考点：版本演进。答：① CRD 声明 v1（served, storage）+ v1beta1（served），配 conversion webhook 互转；② 只有 v1 是 storage（真正写 etcd）；③ conversion 必须无损往返（v1→v1beta1→v1 等价）；④ 等客户端改用 v1；⑤ 下线 v1beta1。webhook 要 HA + 证书自动轮换 + 充分测试。

**Q22. Operator 的 reconcile_errors_total 持续增长，怎么定位？**

考点：可观测排障。答：这是第一告警指标，意味着 Controller 反复失败重试。看日志（error 原因）、events（业务事件）、具体 CR 的 status.conditions。常见原因：CR 配置违反业务规则、子资源 schema 不匹配、apiserver 限流、依赖（外部 API/对象存储）不可达、代码 bug。定位后修复，errors 应回落。

**Q23. 多租户 AI 平台，一个集群多个团队，Operator 怎么隔离？**

考点：多租户。答：两种模式——namespace 级（每团队一 ns + 一 Operator 实例 WATCH_NAMESPACE 限定，简单但运维 N 个 Operator）或集群级（一 Operator + RBAC 严格隔离 CR 写权限，省资源）。配额用 validating webhook 编码（拦截超 GPU 配额的 CR）。工作负载用 nodeSelector/priorityClass 调度到专属节点池。

**Q24. 什么场景**不**该用 Operator？**

考点：选型判断。答：只要"装一次 + 参数多"用 Helm；"一次性流水线 DAG"用 Argo Workflow；"定时/一次性任务"用 Job/CronJob。只有"持续自愈 + 领域知识 + 多资源协同"三者俱全才值得 Operator。很多"看起来需要 Operator"的需求，Helm + readiness probe 就够了——过度工程是反模式。

## 本章小结

- **初级**抓本质：Operator = CRD + 控制循环、与 Helm 互补、Reconcile 四铁律、For/Owns、spec/status、finalizer/owner。
- **中级**抓工程：Manager/Controller 分层、Cache 读写分离、Workqueue 去重、Requeue 四语义、乐观并发、generation 追踪、Leader Election、Webhook 三类、envtest 测试。
- **高级**抓生产：finalizer 卡删除排查、漂移自愈、金丝雀设计、CRD 版本演进、reconcile_errors 排障、多租户隔离、选型判断。

**参考来源**

- 本手册第 1–9 章（全部机制与工程要点）。
- [Kubebuilder FAQ](https://book.kubebuilder.io/)、[controller-runtime 设计文档](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg)。
- 真实参考：[KubeRay](https://github.com/ray-project/kubebuilder)、[Training Operator](https://github.com/kubeflow/training-operator)、[GPU Operator](https://github.com/NVIDIA/gpu-operator)。
