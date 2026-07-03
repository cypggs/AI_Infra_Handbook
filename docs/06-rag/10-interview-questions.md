# 面试题

本章按初级、中级、高级三个层次整理 RAG 相关面试题，并给出参考答案要点。

## 初级

### 1. 什么是 RAG？它解决了 LLM 的什么问题？

**要点**：RAG = Retrieval-Augmented Generation。在生成前检索外部知识，解决知识过时、幻觉、私域知识缺失。

### 2. RAG 和 Fine-tuning 有什么区别？

**要点**：RAG 动态查资料，不改模型参数；Fine-tuning 把知识/风格内化到参数中，训练成本高、知识固化。两者互补。

### 3. 常见的分块策略有哪些？

**要点**：固定长度、重叠窗口、按结构（Markdown/标题）、语义分块、Agentic 分块。

### 4. 什么是 Embedding？它在 RAG 中的作用是什么？

**要点**：把文本映射为稠密向量，用于语义相似度检索。

### 5. Dense Retrieval 和 Keyword Retrieval 各有什么优缺点？

**要点**：Dense 语义泛化好，Keyword 精确匹配强。实际常用 Hybrid。

## 中级

### 6. 如何评估 RAG 系统的效果？

**要点**：检索指标 Hit Rate、MRR、Recall@K、NDCG@K；生成指标 Faithfulness、Answer Relevance；端到端 RAGAS。

### 7. 什么是 RRF？为什么需要它？

**要点**：Reciprocal Rank Fusion 融合多路检索的排名，不需要归一化分数，鲁棒性强。

### 8. Reranker 通常放在流水线的什么位置？为什么？

**要点**：放在检索之后、生成之前；对 Top-K 候选精排，控制成本与延迟。

### 9. 如何处理检索结果为空的情况？

**要点**：查询改写、放宽 metadata 过滤、multi-query、fallback 回答“不知道”。

### 10. 生产环境如何保证多租户数据隔离？

**要点**：独立 collection（物理隔离）或共享索引 + tenant_id metadata 过滤；API 层校验 tenant；审计日志。

## 高级

### 11. 如何设计一个可水平扩展的 RAG 服务？

**要点**：无状态 API 层、独立 embedding 服务、分布式向量库、异步索引 pipeline、缓存层、可观测。

### 12. RAG 中的幻觉引用如何检测与消除？

**要点**：后处理校验引用编号是否存在；用 NLI/LLM 验证答案是否被上下文支持；降低 temperature；拒绝低置信度回答。

### 13. 如何优化 RAG 的端到端延迟？

**要点**：ANN 索引、减小 chunk、缓存、轻量 reranker、异步 embedding、模型路由、流式输出。

### 14. GraphRAG 与传统向量 RAG 的区别是什么？适用场景？

**要点**：GraphRAG 引入实体关系图谱，适合跨文档推理、关系复杂场景；传统向量 RAG 适合文档问答。

### 15. 如果业务要求答案必须来自最新文档，你会怎么设计？

**要点**：metadata 中记录 updated_at；检索/重排中加入 freshness 权重；增量/流式更新索引；答案里显示文档时间。

## 小结

面试题覆盖了概念、实现与生产三个层面。准备时建议结合自己实际项目：你选了什么 chunking/embedding/retrieval 方案？评估指标是多少？线上遇到过哪些 bad case？如何迭代？
