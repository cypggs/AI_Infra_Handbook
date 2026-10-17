# 延伸阅读

## 论文与博客（按主题脉络）

**奠基**

- [From Local to Global: A Graph RAG Approach to Query-Focused Summarization（arXiv 2404.16130）](https://arxiv.org/abs/2404.16130) —— 微软 GraphRAG 论文。实体图谱 + Leiden 层次社区摘要 + local/global 检索的完整配方；评测用 LLM 评审的全面性/多样性/可行动性三维。
- [LazyGraphRAG: Setting a New Standard for Quality and Cost（微软研究院博客，2024-11）](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/) —— 延迟索引思想与官方基准（索引成本约 0.1%、全局查询约 1/700）。
- [DRIFT Search（GraphRAG 官方文档）](https://microsoft.github.io/graphrag/query/drift_search/) —— Dynamic Reasoning and Inference with Flexible Traversal 的机制说明。

**轻量与特化路线**

- [LightRAG: Simple and Fast Retrieval-Augmented Generation（arXiv 2410.05779）](https://arxiv.org/abs/2410.05779) —— 图 + 向量双索引与双层检索；EMNLP 2025 Findings 接收。
- [HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models（arXiv 2405.14831）](https://arxiv.org/abs/2405.14831) —— OpenIE + PPR 的单步多跳检索，NeurIPS 2024。
- [From RAG to Memory: Non-Parametric Continual Learning for Large Language Models（HippoRAG 2, arXiv 2502.14802）](https://arxiv.org/abs/2502.14802) —— 更深的 passage 整合与在线 LLM 过滤，ICML 2025。
- [KAG: Boosting LLMs in Professional Domains via Knowledge Augmented Generation（arXiv 2409.13731）](https://arxiv.org/abs/2409.13731) —— 蚂蚁 OpenSPG 的逻辑形式引导推理框架。

**评估与冷静期**

- [When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation（arXiv 2506.05690）](https://arxiv.org/abs/2506.05690) —— GraphRAG-Bench：系统回答"图什么时候有用"，结论对早期宣传有重要校正。
- [Leiden 算法论文（Traag, Waltman & van Eck, 2019）](https://www.nature.com/articles/s41598-019-41695-z) —— 社区检测的连通性保证，GraphRAG 选它的原因。

**图算法基础**

- [Personalized PageRank（Bahmani et al., WSDM 2010）](https://cs.stanford.edu/~plofgren/scalable_ppr_via_multiplication_wsdm2010.pdf) —— 快速 PPR 估计，HippoRAG 检索的算法地基。
- [GQL 成为 ISO 标准图查询语言（2024）](https://www.iso.org/standard/76120.html) —— Cypher 方言的标准化背景。

## 开源仓库

- [microsoft/graphrag](https://github.com/microsoft/graphrag) —— 参考实现。verb 化流水线、verb 级缓存、prompt 自动调优；截至 2026-10 最新 v3.3.0，进入维护模式。
- [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) —— 生产化最快的社区实现：多后端存储、Server/WebUI、RAGAS + Langfuse、多模态 RAG-Anything。
- [OSU-NLP-Group/HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) —— PPR 多跳检索官方实现（NeurIPS 2024 / ICML 2025）。
- [gusye1234/nano-graphrag](https://github.com/gusye1234/nano-graphrag) —— 约 1100 行的极简实现，读源码的最佳入口。
- [OpenSPG/KAG](https://github.com/OpenSPG/KAG) —— 蚂蚁知识增强生成框架，专业域方案。

## 手册内回链

- [RAG](/06-rag/) —— 图检索之上的通用 RAG 流水线：chunking、rerank、生成策略。
- [向量数据库与 Embedding 基础设施](/06-rag/vector-db/) —— 混合检索中的向量侧：HNSW、量化、Embedding 服务与选型。
- [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/) —— 多跳基准的防污染与 LLM-as-judge 方法论。
- [存储系统](/01-foundation/storage-systems/) —— 图数据库底层：索引、事务、分层存储。
- [分布式系统](/01-foundation/distributed-systems/) —— 分布式图存储的分区、一致性与批量隔离。

## Mini Demo

本主题配套 `mini-demo/`（`graphrag_mini` 包）：纯 Python 确定性实现抽取、建图、社区检测、社区摘要与三种查询模式，78 个测试全绿。运行方式与场景说明见[第 7 章](07-mini-demo)；代码路径：`docs/06-rag/graphrag/mini-demo/`。
