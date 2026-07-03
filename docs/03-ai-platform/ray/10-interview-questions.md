# 10. 面试题精选

> 按初、中、高级整理 Ray 相关的面试题，覆盖概念、源码、工程实践与生产落地。答案要点提示在每题后方。

---

## 10.1 初级

### Q1. Ray 的三个核心抽象是什么？请简述各自特点。

**答案要点**：Task（无状态远程函数，默认 `max_retries=3`）、Actor（有状态进程，默认不重启）、Object（分布式不可变对象，ObjectRef 是未来）。

### Q2. `ray.get` 与 `ray.wait` 的区别是什么？

**答案要点**：
- `ray.get(ref)`：阻塞直到对象可用，返回实际值；列表输入保持顺序。
- `ray.wait(refs, num_returns=1, timeout=None)`：返回 `(ready, unready)` 两个列表；非阻塞式批量等待。

### Q3. 为什么 Ray 的对象是不可变的？

**答案要点**：不可变才能无锁地在多个节点对象存储中复制，无需同步；ObjectRef 指向的值一旦创建不可修改。

### Q4. Actor 的方法调用是并发的吗？

**答案要点**：同一 actor 的方法默认按调用顺序**串行**执行；不同 actor 之间并行。可用 `max_concurrency` 或 async actor 提高并发。

### Q5. 一个 task 失败后会发生什么？

**答案要点**：默认 `max_retries=3`，Ray 会在其他 worker 上重试；超过后向调用方抛异常。可通过 `retry_exceptions` 控制哪些异常触发重试。

---

## 10.2 中级

### Q6. 解释 Ray 的 ownership 模型，以及它如何影响容错。

**答案要点**：
- ObjectRef 的 owner 是创建它的 worker（driver 或另一个 worker）。
- 任务规格、对象元数据、引用计数由 owner 维护，而非全局 GCS 调度器。
- owner 死亡 → 其 ObjectRef 对应的对象不可解析（`OwnerDiedError`），即使对象数据还在其他节点。
- task 生成的对象可通过 owner 保存的任务规格做 lineage 重建；`ray.put` 和小内联对象不可重建。

### Q7. 什么是 spillback scheduling？Ray 为什么从全局调度器转向它？

**答案要点**：
- 旧版 Ray（SOSP'18）有中央 Global Scheduler，瓶颈明显。
- 新版 ownership + spillback：提交者本地 raylet 先尝试调度；若本地资源不足，把任务“溢出”到其他 raylet，逐跳问询。
- 优点：去中心化、可扩展、减少 GCS 负载。

### Q8. Ray 默认的调度策略是 HYBRID，请描述其决策过程。

**答案要点**：
1. 按 argument 本地性给节点排序（持有输入对象的节点优先）。
2. 取 top-k（约 20%）节点。
3. 若最佳节点关键资源利用率超过 `spread_threshold`（默认 0.5），则在 top-k 中选利用率最低的节点（摊平）；否则打包到最佳节点。

### Q9. Object Store 的容量默认如何计算？什么情况下会触发 spilling？

**答案要点**：
- 默认 `min(max(30% RAM, 75 MB), 200 GB on Linux / 2 GB on macOS)`。
- 当 evictable 对象占用超过 `object_spilling_threshold`（默认 80%）时，按 LRU 溢写到本地磁盘。
- primary 对象被引用计数钉住，不会直接被 LRU 驱逐，但释放后变为 evictable。

### Q10. Placement Group 的四种策略有什么区别？各适合什么场景？

**答案要点**：
- `STRICT_PACK`：所有 bundle 必须在同一节点（硬约束）。适合 NVLink 多 GPU。
- `PACK`：尽量同一节点（软约束）。
- `STRICT_SPREAD`：每个 bundle 必须在不同节点（硬约束）。适合 gang-scheduled DDP。
- `SPREAD`：尽量分散（软约束）。适合提高可用性。

### Q11. 为什么 production 不推荐把 GCS 当作 KV 存储或状态中心？

**答案要点**：GCS 默认内存存储、单点瓶颈；现代 Ray 通过 ownership 模型已把任务元数据下沉到 CoreWorker。大量读写 GCS 会导致 Dashboard 卡顿、调度延迟。状态应使用外部存储。

### Q12. Ray Serve 的 autoscaling 配置中，`target_num_ongoing_requests_per_replica` 过小或过大分别有什么后果？

**答案要点**：
- 过小：副本数频繁抖动，冷启动 overhead 高。
- 过大：单副本过载，尾部延迟升高。
- 需根据模型推理 P99 与并发能力调优。

---

## 10.3 高级

### Q13. 设计一个基于 Ray 的大规模批量推理系统，要求支持 GPU 动态扩缩容、任务级重试、结果持久化到 S3。

**答案要点**：
- 用 Ray Data 读取输入（流式分块、S3 输入）。
- `map_batches` 指定 `num_gpus=1` 与 `concurrency`。
- 用 Ray Train/Serve 或 Autoscaler 根据 pending GPU demand 扩容；GPU 节点设置合适 idle timeout。
- task 设置 `max_retries` 与 `retry_exceptions`；失败记录到 DLQ。
- 结果通过 Ray Data `write_parquet` 或 task 内直接写 S3。
- 监控：object store、GPU 利用率、autoscaler pending nodes。

### Q14. 一个 Ray 集群出现“有空闲 GPU 但任务一直 pending”的现象，你会如何排查？

**答案要点**：
1. `ray status` 看资源碎片与 placement group 占用。
2. Dashboard Cluster 视图检查是否有 actor 声明了整块 GPU 但利用率低。
3. 检查 task/actor 资源声明是否匹配实际（如 actor 默认 num_cpus 调度/执行不一致）。
4. 检查是否有 stuck 的 placement group。
5. 查看 scheduler unscheduleable metrics。

### Q15. 如何理解 Ray 中 actor 的“重启后状态丢失”问题？有哪些缓解方案？

**答案要点**：
- actor 是内存状态；`max_restarts` 只重启进程，不恢复状态。
- 缓解：① 状态外置到 Redis/DynamoDB/RDBMS；② 定期 checkpoint 到共享存储；③ 设计幂等方法，重启后从 checkpoint 重放；④ Serve 部署用多副本 + 无状态设计。

### Q16. 在 KubeRay 中启用 Ray Serve 的故障转移（FT）需要哪些条件？GCS FT 的局限是什么？

**答案要点**：
- 需要 Redis 作为 GCS 后端；官方仅支持 KubeRay + Ray Serve FT 场景。
- 局限：增加运维复杂度；Redis 本身成为瓶颈与单点；非 Serve 场景官方支持有限。

### Q17. 比较 Ray Core 手写 task graph 与 Ray Data 处理大数据集的 trade-off。

**答案要点**：
- 手写 task：灵活、细粒度控制；但容易 ObjectRef 泄漏、shuffle 实现复杂、object store OOM。
- Ray Data：流式执行、自动批处理、内置 shuffle/重新分区、与对象存储集成；但抽象层固定，极端自定义场景可能受限。

### Q18. Ray 的 ownership 模型与 Spark 的 driver-centric 调度模型有什么本质区别？

**答案要点**：
- Spark driver 持有完整 DAG 与 stage 调度；task 由 driver 统一分配。
- Ray 把任务规格与引用计数分散到每个 CoreWorker（owner）；调度是分布式 spillback。
- 结果是 Ray 更擅长动态、细粒度、异构 DAG；Spark 更擅长批处理 SQL/DataFrame 优化。

### Q19. 你如何测试一个 Ray 应用的容错逻辑？

**答案要点**：
- 单元测试：本地 `ray.init()` + `max_retries` 验证。
- 集成测试：用 `ray.cluster_utils.Cluster` 模拟多节点；调用 `kill_node` 或自定义 fail_node。
-  chaos 测试：在 staging 集群随机 kill worker pod，验证 checkpoint 与重试。
- 断言：任务成功完成、重建次数符合预期、OwnerDiedError 在不可重建场景正确抛出。

### Q20. 设计一个“教育版 Ray 模拟器”来展示 ownership + lineage reconstruction，你会保留哪些核心机制、简化哪些？

**答案要点**：
- 保留：ObjectRef 的 owner/generating_task/small_inline 属性、hybrid 调度分数、对象存储三层、任务依赖与重建、显式节点失败。
- 简化：单线程同步 tick、无真实网络、driver 统一作为 owner、actor 仅做状态占位、调度全局分数而非分布式 spillback。
- 教学价值：用确定性行为展示“worker 失败但 owner 存活 → 重建成功”与“owner 死亡 → OwnerDiedError”。

---

## 10.4 场景设计题

### S1. 旅行规划 Agent 的 Ray 后端

需求：用户输入自然语言旅行请求，系统拆解为“查航班、查酒店、算总价、生成行程”，支持某一步失败时重试/替代方案。

**设计思路**：
- 用 Ray task 实现每个工具调用；工具失败抛异常，设置 `max_retries=2`。
- 用 DAG 依赖控制执行顺序：航班/酒店可并行，总价依赖前两者，行程依赖总价。
- 结果对象由 task 生成，可重建；用户会话状态用 actor 维护。
- 超时控制：`ray.get(..., timeout=30)`，超时后触发 fallback。

### S2. 多租户 GPU 训练平台

需求：多个团队共享一个 GPU 集群，需要隔离、优先级、抢占、checkpoint。

**设计思路**：
- KubeRay 多 `RayCluster` 或 namespace 隔离；或用 Placement Group + 自定义队列做软隔离。
- 优先级：通过外部调度器（如 Volcano/Yunikorn）或自研 admission queue。
- 抢占：低优先级 actor/task 可被 kill；训练任务需高频 checkpoint。
- 监控：按团队/项目打 tag，聚合 GPU 利用率与排队时间。

---

## 10.5 小结

- 初级：掌握核心抽象、API 语义、默认参数。
- 中级：理解 ownership、调度策略、对象存储、placement group。
- 高级：能设计系统、排查生产问题、权衡手写 task graph vs 高层库。
- 通用能力：把 Ray 机制与真实 workload 特征匹配，而不是死记硬背参数。
