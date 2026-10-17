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

**要点**：GraphRAG 引入实体关系图谱，适合跨文档推理、关系复杂场景；传统向量 RAG 适合文档问答。还要能说出 Microsoft GraphRAG（社区摘要、索引贵）、LightRAG（双层检索、更新友好）、HippoRAG（PPR 多跳）的差异。

### 15. 如果业务要求答案必须来自最新文档，你会怎么设计？

**要点**：metadata 中记录 updated_at；检索/重排中加入 freshness 权重；增量/流式更新索引；答案里显示文档时间。

### 16. “RAG 已死，长上下文就够了”这个观点对吗？（2025–2026 高频题）

**要点**：不对，是互补。LaRA（ICML 2025）：长上下文强于比较/推理，RAG 强于幻觉抑制与恰当拒绝；NoLiMa：标称 128K 的模型多数 32K 内就严重衰减，有效上下文远小于标称；成本上长上下文可达 RAG 的数十倍。生产共识是“检索粗筛 + 长上下文精读”，配合 Prompt Caching。

### 17. 什么是 Contextual Retrieval？为什么有效？

**要点**：Anthropic 2024 提出，嵌入前为每个 chunk 生成文档级上下文说明再嵌入，官方报告检索失败率 5.7% → 2.9%，叠加 BM25 混合与重排后 1.9%。代价是每个 chunk 一次 LLM 调用，适合离线摊薄。

### 18. 什么是 Agentic RAG？相比单次 RAG 的收益与代价？

**要点**：模型自主决定何时检索、检索什么、何时停止（Search-R1/ReSearch 用 RL 训练）。有行业评测显示多跳问答准确率可从 34% 提升到 78%，但 token 约 3 倍、延迟约 4 倍；到 2026 年这一模式已从论文进入生产默认（LangGraph/LlamaIndex 模板、Dify Agent 节点），工程上必须配路由、迭代预算、grader 节点与轨迹可观测，按 cost per correct answer 评估。

### 19. 推理模型时代，查询改写/query 生成有什么变化？

**要点**：推理模型在“知道自己缺什么”的推理中途发起检索，查询质量优于一次性改写；需要把检索工具化（schema、截断、引用编号），并处理检索与推理上下文交织的问题（如 retrieved-token masking 的训练技巧）。

### 20. Late Chunking 与多模态检索（ColPali）解决了什么问题？

**要点**：Late Chunking 先整篇嵌入再切分，让 chunk 向量携带全文上下文；ColPali 把 PDF 页直接编码为多向量视觉表示、用 MaxSim 检索，绕过脆弱 OCR/解析流水线，代价是索引存储放大与 late interaction 推理开销。

### 21. Contextual Retrieval 与 Contextual Embedding 有什么区别？（2026 高频题）

**要点**：两者目标相同——让 chunk 向量携带文档级上下文；区别在于实现与成本。Contextual Retrieval（Anthropic）在索引期用 LLM 为每个 chunk 预生成上下文说明再嵌入，检索失败率 5.7% → 1.9%（叠加混合检索与重排），但每个 chunk 一次 LLM 调用、索引成本高，适合离线批处理；Contextual Embedding（voyage-context-3/4）由编码器在编码时内生整篇文档上下文，索引期零额外 LLM 调用、vendor 报告 chunk 级检索较 text-embedding-3-large 提升约 14%，适合高频更新语料。选型看索引预算与更新频率。

### 22. 2026 年开源 Reranker 怎么选？需要注意什么？

**要点**：精度优先选 Qwen3-Reranker（0.6B/4B/8B，Apache-2.0，4B 是精度/延迟甜点）；低延迟长上下文选 jina-reranker-v3/v3.5（listwise、约百毫秒级、131K 上下文），但它是 CC-BY-NC 非商用许可，商用自托管必须避开；预算敏感选 BGE-Reranker-v2-m3（Apache-2.0）。核心注意点是**许可证**与 **Top-K 截断位置**（reranker 只处理召回头部，成本可控）。

## 小结

面试题覆盖了概念、实现与生产三个层面。准备时建议结合自己实际项目：你选了什么 chunking/embedding/retrieval 方案？评估指标是多少？线上遇到过哪些 bad case？如何迭代？
