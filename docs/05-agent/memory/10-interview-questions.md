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
- **性能**：检索/写入延迟 P50/P99、存储成本。
- **隐私合规**：敏感信息拦截率、用户删除响应时间。

## 本章小结

Agent Memory 的面试问题通常集中在：**记忆分类与生命周期**、**向量检索策略**、**长期记忆与 RAG 的区别**、**多租户隔离**、**embedding 模型管理**、**遗忘与更新机制**、**隐私与安全**、**Memory 与 Runtime 的边界**。掌握本章问题，基本可以覆盖初级到高级面试场景。

**参考来源**

- [Letta Documentation](https://docs.letta.com)
- [LangGraph Memory Concepts](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
- [MemGPT Paper](https://arxiv.org/abs/2310.08560)
