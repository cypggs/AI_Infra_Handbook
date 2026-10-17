# 向量数据库与 Embedding 基础设施

Embedding（嵌入向量）已经成为继字符串、数字、JSON 之后的又一"一等公民"数据类型。RAG、语义搜索、推荐、Agent 记忆、多模态检索，底层都依赖同一件事：**在高维向量空间里快速找到最相似的 k 个邻居**。向量数据库与 Embedding 基础设施主题聚焦这条基础设施链路本身——向量索引算法（HNSW、IVF-PQ、DiskANN）、向量数据库系统（Milvus、Qdrant、pgvector……）、量化压缩、GPU 检索与 Embedding 推理服务。

## 一句话理解

> 向量数据库是"以相似度为查询语义"的数据库：它把"找出和这句意思最接近的一亿条文本"从不可计算的问题，变成毫秒级、可运维、可扩展的工程系统。

## 学习目标

读完本主题后，你应该能够：

- 解释为什么精确最近邻（Exact NN）在高维空间不可行，以及近似最近邻（ANN）如何用"召回率换延迟"。
- 讲清三大索引家族——近邻图（HNSW/Vamana）、倒排量化（IVF-PQ）、树/哈希——的设计取舍，以及 ef、M、nlist、nprobe 等关键参数的作用。
- 描述一个向量数据库的完整架构：接入层、协调器、索引构建、查询执行、WAL 与对象存储，以及 Milvus 2.6 的 Streaming Node / Woodpecker WAL 这类新组件为什么出现。
- 掌握量化体系：SQ、PQ、BQ/1-bit（RaBitQ）、标量量化与 Refine，以及它们对内存、召回率的影响曲线。
- 说出 GPU 向量检索（NVIDIA cuVS / CAGRA）的定位：什么时候值得上 GPU，什么时候只是"GPU 建索引、CPU 做服务"的加速卡。
- 选型：在 Milvus、Qdrant、Weaviate、pgvector、LanceDB、Redis、Elasticsearch 之间做出有依据的选择。
- 设计 Embedding 服务基础设施：模型选型（OpenAI text-embedding-3、BGE-M3、Qwen3-Embedding 等）、推理服务（TEI、Infinity）、版本管理与重建策略。
- 避开生产陷阱：过滤检索的 post-filter 陷阱、删除与一致性、十亿级规模的成本估算。

## 与相邻主题的关系

| 相邻主题 | 与本主题的关系 |
|---|---|
| [RAG](/06-rag/) | RAG 讲"怎么用检索增强生成"；本主题讲"检索系统本身怎么工作、怎么运维"。RAG 是本主题最大的下游消费者。 |
| [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/) | 向量检索的召回率评估、Embedding 模型的 MTEB 榜单解读，都需要评估方法论与防污染纪律。 |
| [vLLM](/04-llmops/vllm/) | vLLM 除生成外也支持 pooling/embedding 推理；Embedding 与 LLM 推理共享 GPU 资源规划逻辑。 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 自建 Embedding 服务通常与 LLM 网关同层部署，统一做限流、鉴权、成本核算。 |
| [存储系统](/01-foundation/storage-systems/) | 向量数据库的 WAL、分层存储、对象存储设计直接继承存储系统的基本原理。 |
| [GPU CUDA](/01-foundation/gpu-cuda/) | GPU 向量索引（CAGRA）与 GPU 推理的资源规划，建立在对 HBM/带宽/并行的理解上。 |
| [分布式系统](/01-foundation/distributed-systems/) | Milvus 的分片、一致性、协调器设计是典型的分布式系统问题。 |
| [Agent Memory](/05-agent/memory/) | Agent 长期记忆几乎都持久化在向量数据库中，其写入/遗忘策略直接影响记忆检索质量。 |

## 章节导航

1. [背景与动机：从 BM25 到稠密向量检索](01-background)
2. [核心概念：ANN、不可能三角与量化](02-core-ideas)
3. [架构设计：向量数据库系统分层](03-architecture)
4. [检索工作流程：从 Insert 到 Query 的完整路径](04-search-workflow)
5. [核心模块：HNSW、IVF-PQ、DiskANN、量化、GPU 索引与过滤检索](05-core-modules)
6. [生态与实现分析：主流系统对比与源码级解读](06-source-analysis)
7. [Mini Demo：纯 Python 实现向量检索最小栈](07-mini-demo)
8. [企业生产实践：选型、十亿级运维与成本](08-production-practice)
9. [最佳实践：参数调优、Over-fetch 与混合检索](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 一句话总结

Embedding 把"语义相似"翻译成了"距离相近"，向量数据库则把高维空间里的最近邻搜索变成了可索引、可量化、可分布、可运维的基础设施——它是 RAG 与 Agent 时代的数据底座。
