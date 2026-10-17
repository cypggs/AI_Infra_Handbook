# GraphRAG 与知识图谱检索

向量检索把"语义相似"变成了"距离相近"，但它有两个结构性盲区：**需要多跳推理的问题**（"A 的核心技术启发了 B 的哪个组件？"）和**面向整个语料库的问题**（"这些文档整体上反映了哪些主题？"）。GraphRAG（Graph Retrieval-Augmented Generation，图检索增强生成）用 LLM 把非结构化文档抽成知识图谱，再在图上做检索，把这两类问题从"检索不到"变成"可计算"。本主题覆盖这一范式的核心思想、分层索引架构、主流开源实现（GraphRAG / LightRAG / HippoRAG / KAG）、成本与评估的生产实践。

## 一句话理解

> GraphRAG 是"先让 LLM 把语料读成一张图，再让图替检索器记住关系"：向量检索回答"哪段话和这个问题像"，图检索回答"哪些实体通过什么关系连在一起、整个语料在讲什么"。

## 学习目标

读完本主题后，你应该能够：

- 解释向量检索在多跳推理与全局（语料级）问题上的结构性缺陷，以及图索引为什么能补上这两块。
- 讲清 GraphRAG 的完整流水线：LLM 实体/关系抽取、Leiden 层次化社区检测、map-reduce 社区摘要，以及 local / global / DRIFT 三种查询模式的差别。
- 区分图索引的三种范式——KG+遍历（HippoRAG）、KG+社区摘要（GraphRAG）、KG+向量双索引（LightRAG）——以及 LazyGraphRAG 的"延迟索引"思路。
- 给出主流实现的横向对比（GraphRAG、LightRAG、HippoRAG 2、nano-graphrag、KAG），并说清各自适用场景。
- 估算 GraphRAG 的索引成本构成，说出分层索引、延迟摘要、prompt 调优等降本手段。
- 设计 GraphRAG 的生产评估方案：多跳基准（2WikiMultihopQA / MuSiQue / HotpotQA）、全局问题评估，以及"什么时候图检索其实没用"的判别纪律。

## 与相邻主题的关系

| 相邻主题 | 与本主题的关系 |
|---|---|
| [RAG](/06-rag/) | RAG 主题把 GraphRAG 列为生态对比的一环；本主题把图检索这一范式展开到底。RAG 的 chunking、rerank、生成策略全部适用于本主题。 |
| [向量数据库与 Embedding 基础设施](/06-rag/vector-db/) | 图检索不取代向量检索：LightRAG 用向量做图内检索，生产实践普遍采用 graph + vector + BM25 混合。向量库是本主题的协作基础设施。 |
| [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/) | GraphRAG 的效果评估依赖多跳问答基准与 LLM-as-judge 方法；该主题的防污染与评估纪律直接适用。 |
| [存储系统](/01-foundation/storage-systems/) | 图数据库（Neo4j / NebulaGraph / Neptune）的存储引擎、索引与事务设计继承存储系统的基本原理。 |
| [分布式系统](/01-foundation/distributed-systems/) | 分布式图存储的分区、一致性与查询路由是典型的分布式系统问题。 |
| [LLM Gateway](/04-llmops/llm-gateway/) | GraphRAG 的索引阶段是 LLM token 消耗大户，生产上需要网关统一做限流、缓存与成本核算。 |
| [Agent Memory](/05-agent/memory/) | 长期记忆的图谱化（Memory 作为可查询的 KG）是 GraphRAG 思想的直接延伸。 |

## 章节导航

1. [背景与动机：向量检索的两个盲区](01-background)
2. [核心思想：局部 vs 全局检索，图索引三范式](02-core-ideas)
3. [架构设计：GraphRAG 分层索引架构](03-architecture)
4. [工作流程：索引与查询的两阶段流水线](04-graphrag-workflow)
5. [核心模块：抽取、社区检测、摘要、图存储与查询路由](05-core-modules)
6. [生态与源码分析：GraphRAG / LightRAG / HippoRAG / KAG 对比](06-source-analysis)
7. [Mini Demo：纯 Python 实现 GraphRAG 最小栈](07-mini-demo)
8. [企业生产实践：成本、增量更新与评估](08-production-practice)
9. [最佳实践：什么时候上图，怎么上图](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 一句话总结

GraphRAG 家族把"检索什么"从相似度问题升级成了图上的结构问题：实体关系图谱负责精确的多跳连接，社区摘要负责全局语料概览，向量检索负责语义兜底——三者混合，才是生产上的完整答案。
