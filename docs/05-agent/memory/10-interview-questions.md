# 10. 面试题

> 一句话理解：**Agent Memory 相关的面试通常围绕“记忆分类、向量检索、生命周期、长期记忆与 RAG 区别、多租户隔离、embedding 选型”六个核心展开**。

## 初级

### Q1：Agent Memory 与 RAG 有什么区别？

**参考答案**：

- RAG 是从外部知识库（企业文档、FAQ、知识图谱）检索固定知识。
- Memory 是 Agent 自身运行过程中积累的用户偏好、对话历史、任务经验。
- 典型关系：两者都可用向量检索，但数据来源不同；生产中可以共用向量数据库，通过 collection 或 metadata 隔离。

### Q2：Agent 为什么需要长期记忆？不能只靠上下文窗口吗？

**参考答案**：

- 上下文窗口长度有限，无法装下多年积累。
- 每次调用都塞满历史会显著增加成本与延迟。
- 模型在大量文本中“自行回忆”命中率低、幻觉风险高。
- 跨会话、跨任务的经验需要显式持久化。

### Q3：工作记忆、短期记忆、长期记忆分别是什么？

**参考答案**：

- **工作记忆**：当前请求直接可见的完整 messages，会话结束或超窗后失效。
- **短期记忆**：当前会话内但已超出工作记忆窗口的信息，常以摘要或滑动窗口存在。
- **长期记忆**：跨会话保留的语义事实、用户偏好、任务经验，通常用向量数据库存储。

## 中级

### Q4：长期记忆和 RAG 都用到向量检索，它们能不能合并？

**参考答案**：

- 可以共用向量数据库基础设施，但应在逻辑上隔离。
- 常用方式：不同 collection、namespace 或 metadata 字段区分来源。
- RAG 检索的是企业知识，Memory 检索的是 Agent 经验，两者回注到 prompt 时也应分开标注来源。
- 合并的好处是统一运维与索引管理；风险是如果隔离不当会导致记忆串味。

### Q5：如何防止 Agent 把错误信息存入长期记忆？

**参考答案**：

- 对存入长期记忆的信息做置信度评估。
- 关键事实要求用户确认后再写入。
- 记录记忆来源，便于后续审计与删除。
- 对工具结果做后置检查，不把明显错误的结果当事实。
- 写入前过输入护栏，防止提示注入污染记忆。

### Q6：向量检索中 dense retrieval 和 sparse retrieval 各有什么优缺点？什么时候用 hybrid？

**参考答案**：

- **Dense retrieval**：基于 embedding 向量，能召回语义相关但字面不同的结果，但对精确匹配（如 ID、订单号）不强。
- **Sparse retrieval**：基于 BM25/TF-IDF，对精确关键词和稀有词效果好，但无法捕捉语义。
- **Hybrid**：结合两者，通常 `score = alpha * dense_score + (1 - alpha) * sparse_score`，适合既需要语义理解又需要精确匹配的场景。

### Q7：多租户场景下如何保证记忆隔离？

**参考答案**：

- 逻辑隔离：每条记忆带 `tenant_id` / `user_id`，检索时强制过滤。
- Namespace 隔离：按租户分 collection / namespace。
- 物理隔离：不同租户使用独立数据库/集群。
- 关键是在数据库层过滤，而不是在应用层过滤；同时审计所有记忆访问。

### Q8：embedding 模型升级时需要注意什么？

**参考答案**：

- 新旧模型向量空间不同，不能直接混用。
- 方案一：用新模型重新编码全部记忆。
- 方案二：双写新旧向量，逐步切换。
- 方案三：给记忆标记 `embedding_model_version`，检索时按版本过滤。
- 需要监控检索质量变化，必要时回滚。

## 高级

### Q9：设计一个生产级 Agent Memory 系统，你会怎么设计？

**参考答案**：

- **接口层**：Memory Service 提供 `remember/recall/forget/update`，供 Agent Runtime 调用。
- **记忆分层**：Working Memory（内存）、Short-term Memory（Redis）、Semantic/Episodic Memory（向量 DB）、Procedural Memory（KV/Postgres）。
- **编码层**：真实 embedding 模型 + 摘要模型 + 实体抽取。
- **存储层**：按类型选向量 DB / KV / 文档 DB / 对象存储。
- **检索层**：hybrid search + rerank + 元数据过滤。
- **生命周期**：TTL + 衰减 + 用户删除 + 敏感信息过滤。
- **多租户**：namespace + 数据库层过滤 + 审计。
- **可观测**：OpenTelemetry trace + Prometheus metrics + 审计日志。
- **隐私**：PII 检测、敏感信息拒绝、用户可控。

### Q10：Agent Memory 中的“遗忘”应该如何实现？

**参考答案**：

- **截断**：超出容量时删除最旧或最低分记忆。
- **摘要压缩**：用摘要替代原始多轮对话。
- **衰减**：给记忆重要性分数，随时间或使用频率衰减。
- **TTL**：按类型设置过期时间。
- **主动删除**：用户请求删除、敏感信息删除、错误记忆删除。
- **冲突更新**：新事实覆盖或版本化旧事实。

### Q11：Memory 与 Agent Runtime 的边界是什么？

**参考答案**：

- **Runtime** 负责决定什么时候调用记忆、把什么传给记忆、把检索结果怎么用。
- **Memory** 负责存储、编码、索引、检索、遗忘本身。
- Runtime 不直接操作向量数据库；Memory 不决定任务如何执行。
- 两者通过 `remember/recall` 契约交互。

### Q12：如何评测 Agent Memory 系统的好坏？

**参考答案**：

- **检索质量**：hit@k、MRR、precision@k。
- **记忆覆盖**：用户偏好/事实被成功记住的比例。
- **污染率**：错误、幻觉、低质量记忆的比例。
- **业务价值**：有记忆 vs 无记忆的任务成功率、用户满意度。
- **性能**：检索/写入延迟 P50/P99、存储成本、每次查询注入的 token 数。
- **隐私合规**：敏感信息拦截率、用户删除响应时间。
- **基准工具**：LoCoMo、LongMemEval、BEAM，以及行动式评测 DolphinBench 与遗忘评测 Bemula；厂商自报分数要谨慎，应自有数据 bake-off。

### Q13：向量记忆和时序知识图谱记忆有什么区别？什么时候选后者？

**参考答案**：

- 向量记忆把记忆编码为稠密向量，擅长语义模糊召回，但表达不了“实体之间的关系”和“事实何时为真”。
- 时序知识图谱（如 Graphiti）把记忆建模为实体 + 关系 + 双时序属性（生效时间/失效时间），新事实到来时旧事实被“失效”而不是删除。
- 选型判断：如果业务事实大量随时间演进（用户偏好变化、组织关系调整、状态流转），且需要回答“以前是什么”“什么时候变的”，选时序图谱；如果只是静态偏好与 FAQ 式事实，向量记忆足够。
- 两者可以组合：向量负责粗召回，图谱负责实体对齐、多跳遍历与时序过滤。

### Q14：什么是 sleep-time compute？它解决了记忆系统的什么问题？

**参考答案**：

- Sleep-time compute 由 Letta / UC Berkeley 提出（arXiv:2504.13171）：让 Agent 在空闲时运行后台 LLM 调用，预处理输入、整理记忆，从而降低测试时（请求路径）计算量（论文报告约 5 倍）。
- 对记忆系统的意义：记忆整理（事实合并、冲突消解、core/archive 升降级）本来要在请求路径上做，延迟高、成本大；移到后台离线做之后，请求路径只需要轻量检索。
- 本质是把记忆的“写入与整理”从同步路径解耦到异步路径，代价是需要维护一个后台 Agent 与触发调度。2026 年 9 月 Mem0 的 Dream 功能把同一思路带到了中间件路线：后台执行 Merge / Supersede / Synthesize，且任何操作都不物理删除记忆。

### Q15：用户要求删除一条记忆，如何保证它真的被删除了？

**参考答案**：

- 难点在于派生链：一条记忆可能已被压缩进摘要、综合成洞察、编码进 embedding、投影到图节点、缓存在检索索引中，逐点删除容易、证明全部清除难。
- 2026 年 10 月的 Bemula 基准（arXiv:2610.18052）显示，主流记忆系统端到端通过遗忘请求的比例不超过 1.5%——这是行业公认短板。
- 工程缓解：写入时保留 provenance（来源指针），删除沿派生链传播；优先用 TTL 与敏感标签前置拦截，减少需要事后清除的数据量；删除操作本身进入审计日志并可验证。

## 本章小结

Agent Memory 的面试问题通常集中在：**记忆分类与生命周期**、**向量检索策略**、**长期记忆与 RAG 的区别**、**多租户隔离**、**embedding 模型管理**、**遗忘与更新机制**、**隐私与安全**、**Memory 与 Runtime 的边界**。2025 年后还会考察**向量 vs 图谱 vs 时序记忆的选型**、**sleep-time compute / 后台记忆整理**（Letta sleep-time、Mem0 Dream）与**行动式记忆评测（DolphinBench）/ 合规遗忘（Bemula）**等新范式。掌握本章问题，基本可以覆盖初级到高级面试场景。

**参考来源**

- [Letta Documentation](https://docs.letta.com)
- [LangGraph Memory Concepts](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Graphiti GitHub（Zep 开源引擎）](https://github.com/getzep/graphiti)
- [Sleep-time Compute（arXiv:2504.13171）](https://arxiv.org/abs/2504.13171)
- [Bemula: Memory Unlearning Benchmark（arXiv:2610.18052）](https://arxiv.org/abs/2610.18052)
- [Mem0 Blog — Dream（2026-09）](https://mem0.ai/blog/dream-background-memory-consolidation-for-ai-agents)
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
- [MemGPT Paper](https://arxiv.org/abs/2310.08560)
