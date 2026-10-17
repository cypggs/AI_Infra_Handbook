# 源码与生态分析

RAG 生态已经高度繁荣。本章选取最具代表性的框架、向量库和模型，分析它们的设计取舍，帮助你在选型时做出理性判断。

## LangChain

- **定位**：LLM 应用编排框架，2025 年 10 月发布 1.0 alpha，2026 年进入稳定的 1.x 快速迭代（2026-10 为 langchain 1.4.x / langchain-core 1.6.x），重心转向 Agent 编排与 middleware 架构。
- **核心抽象**：`DocumentLoader`、`TextSplitter`、`Embeddings`、`VectorStore`、`Retriever`、`Runnable` 接口。
- **RAG 模式**：`create_retrieval_chain`、`ConversationalRetrievalChain`、`MultiQueryRetriever`、`ContextualCompressionRetriever`。
- **Agentic 演进**：Agent 能力已迁移到 **LangGraph**（图状态机编排）：节点是检索/工具/LLM，边是路由与循环，天然支持“检索—反思—再检索”的迭代模式，是 2025 年后 Agentic RAG 的主流编排底座。1.x 主线的新增重心是可插拔 **middleware**（HITL 中断、Summarization 等）与跨 provider 的 model profiles。
- **优点**：生态最广、上手快、文档丰富。
- **缺点**：抽象层级多，生产调试复杂；版本迭代快，API 兼容性需要关注。

## LlamaIndex

- **定位**：以 RAG 和数据为中心的 LLM 应用框架。
- **核心抽象**：`Node`（chunk）、`Index`、`Retriever`、`QueryEngine`、`ResponseSynthesizer`。
- **RAG 模式**：
  - `VectorStoreIndex` + `as_query_engine()`。
  - `SubQuestionQueryEngine` 自动分解复杂查询。
  - `RouterQueryEngine` 按查询选择不同索引/工具。
- **Agentic 演进**：2025 年推出 **Workflows** 事件驱动运行时，Agent 统一迁移其上；2026 年 Workflows 已演进到 2.x（llama-index 主包 0.14.x，2026-09 为 0.14.25），并加入多模态 query engine、tools-mcp 对 MCP 2.x 协议的适配，最低 Python 版本升至 3.10。数据摄取、结构化检索、GraphRAG（PropertyGraphIndex）仍是其最强项。社区共识是“LlamaIndex 做数据/索引层 + LangGraph 做编排层”的组合。
- **优点**：RAG 场景抽象更自然，支持高级检索（递归、摘要、图）。
- **缺点**：学习曲线略陡，部分高级功能绑定 LlamaIndex 生态。

## Haystack

- **定位**：面向企业的 NLP/RAG Pipeline 框架（2.x），强调流水线组件化。
- **核心抽象**：`Component`、`Pipeline`、`DocumentStore`、`Retriever`、`Reader`/`Generator`。
- **RAG 模式**：
  - `Pipeline` 用 YAML/代码定义：Preprocess → Embed → Retrieve → Rerank → Generate。
  - 支持多种 DocumentStore（OpenSearch、Pinecone、Weaviate、Qdrant、Milvus）。
- **优点**：流水线可视化、企业级集成友好。
- **缺点**：社区活跃度相对 LangChain/LlamaIndex 较低。

## 评估框架：RAGAS / ARES / TruLens

- **RAGAS**（[GitHub](https://github.com/explodinggradients/ragas)）：最流行的开源 RAG 评估框架。**0.4 系列（2025 年 12 月发布 0.4.0，2026-01 为 0.4.3）**把指标全面迁移到 collections API 与 BasePrompt 架构，原生支持 GPT-5/o 系列模型，新增 DSPyOptimizer（MIPROv2）提示优化与指标/embedding 缓存——这些改动都是为了让评估指标更容易嵌入 CI 与在线 trace 持续运行，而不是一年跑一次离线报告。
- **ARES**：用“轻量打分段 + 少量人工标注 + LLM 评判”以极低成本评估 context relevance / faithfulness / answer relevance，适合没有标注团队的小团队做粗粒度回归。
- **TruLens**：以 feedback function 为核心的评估与追踪一体化方案，与 OpenTelemetry 生态结合紧密，适合把评估逻辑与可观测平台合并部署。

2026 年的实践共识：评估框架与 trace 平台（Langfuse、LangSmith、Arize Phoenix）合并部署，把 RAGAS 类指标作为在线 judge 持续运行；Agentic 链路额外记录轨迹级指标（迭代轮数、停止时机、cost per correct answer）。

## RAGFlow / Dify / FastGPT

| 产品 | 定位 | 特点（2026 年视角） |
|---|---|---|
| **RAGFlow** | 开源深度文档 RAG 引擎 | DeepDoc 文档解析最强，适合复杂 PDF/合同/财报；支持 GraphRAG 与知识图谱检索；资源消耗较大，Workflow 能力弱于 Dify |
| **Dify** | LLM 应用开发平台 | 社区最活跃的开源平台之一，可视化编排、知识库、Agent、模型管理最全面；企业级首选，但不支持知识图谱检索 |
| **FastGPT** | 轻量知识库问答平台 | 部署最简单、中文优化好，适合中小团队快速落地 |

这些工具适合快速搭建与业务迭代，但在大规模、多租户、强治理场景下通常需要二次开发或自建核心链路。选型经验：工程师少（不足 1 人投入）→ FastGPT/Dify；文档复杂 → RAGFlow；需要深度定制与 Agentic 编排 → LangChain/LlamaIndex 自建。Flowise 等拖拽式低代码工具适合原型验证，进入生产时通常让位于上述平台。

## 向量数据库与索引库

| 产品 | 类型 | 特点 |
|---|---|---|
| **Milvus/Zilliz** | 分布式向量数据库 | 云原生、分片、多副本；2.5 起内置全文索引，混合检索开箱即用 |
| **Pinecone** | 托管向量数据库 | 免运维、metadata 过滤、hybrid search |
| **Weaviate** | 向量+语义数据库 | GraphQL 接口、模块化、本地/云 |
| **Qdrant** | 向量数据库 | Rust 实现、过滤性能强、自托管友好 |
| **Vespa** | 搜索引擎+向量 | 多向量/张量检索成熟，ColBERT/ColPali 部署首选之一 |
| **Chroma** | 嵌入式向量库 | 本地开发友好，不适合大规模生产 |
| **pgvector** | Postgres 扩展 | 与 SQL 生态集成，适合已有 PG 的团队 |
| **Faiss** | 索引库 | 高性能 ANN，需自管存储与分布式 |
| **Elasticsearch/OpenSearch** | 搜索引擎 | 混合检索成熟，BM25 + dense 结合方便 |

## Embedding 与 Reranker 模型

| 模型 | 类型 | 说明 |
|---|---|---|
| OpenAI text-embedding-3 | Dense | 综合能力强，API 调用方便 |
| Qwen3-Embedding | Dense | 0.6B/4B/8B，32K 上下文，2025-06 登顶 MTEB 多语言榜 |
| Qwen3-VL-Embedding / Reranker | 多模态 | 2B/8B，32K，Apache-2.0，视觉文档检索（MMEB-V2）+ reranker 一体（[arXiv:2601.04720](https://arxiv.org/abs/2601.04720)，2026-01） |
| voyage-context-3 / -4 | Dense（内生上下文） | chunk 向量自动携带文档级语境，索引期零额外 LLM 调用；v4 单请求窗口 120K 并内置自动分块 |
| BGE / BGE-M3 | Dense/Sparse | 中文/多语言表现好，支持多模态/长文本 |
| jina-embeddings-v3 | Dense |  late chunking 配套的长上下文模型，多语言 |
| E5 / E5-mistral | Dense | Microsoft 开源，通用检索强 |
| GTE-Qwen | Dense | 阿里开源，中文场景优秀 |
| Cohere Rerank 3.5 | Reranker | API 版，商用精度标杆之一 |
| Qwen3-Reranker | Reranker | 开源生成式打分（是/否 token），Apache-2.0，多档参数规模（4B 为甜点档） |
| jina-reranker-v3 / v3.5 | Reranker | listwise，约百毫秒级延迟、131K 上下文，CC-BY-NC 非商用许可 |
| BGE-Reranker-v2-m3 | Reranker | 开源可部署（Apache-2.0），性价比好 |
| ColBERT / ColPali | Late Interaction | 多向量检索；ColPali 面向视觉文档（ICLR 2025），Vespa/ViDoRe 生态支撑生产化 |

## GraphRAG：从 Microsoft GraphRAG 到 LightRAG 与 HippoRAG

GraphRAG 在向量检索之上引入知识图谱，2025 年生态明显分化：

- **Microsoft GraphRAG**：原始代表。索引阶段对每个 chunk 做实体/关系抽取，再分层聚类生成社区摘要；查询阶段按 local/global 两种模式分别走向量检索或社区摘要。优点是全局综合（“这份语料整体讲了什么”）能力强；**缺点是索引成本高**（每个 chunk 一次 LLM 调用 + 分层摘要），语料更新困难。
- **LightRAG**（[GitHub](https://github.com/HKUDS/LightRAG)，EMNLP 2025）：轻量化替代。同样建图谱，但采用**双层检索**——低层实体检索 + 高层关系/主题检索——避免昂贵的社区摘要；支持文档删除与图谱增量再生、Reranker 接入，工程上更贴近生产。
- **HippoRAG / HippoRAG 2**：受神经科学记忆启发的路线——知识图谱 + Personalized PageRank 做**多跳关联检索**，把“联想记忆”显式建模；2 代加入 passage 节点与识别记忆过滤，索引成本显著低于前两者。多跳推理任务优势明显，单跳事实问答不必用它。

实践结论：图谱路线的选型主要看**索引成本、更新频率、查询是多跳还是单跳**；简单事实问答用混合向量检索即可，跨文档关系推理与全局综合才值得付出建图谱的成本。

## Agentic RAG 的代表实现

| 工作 | 来源 | 思路 |
|---|---|---|
| **CRAG** | 2024，[arXiv:2401.15884](https://arxiv.org/abs/2401.15884) | 检索结果轻量打分，分 Correct/Ambiguous/Incorrect 三档，触发修正或补充检索 |
| **Search-R1** | 2025，[arXiv:2503.09516](https://arxiv.org/abs/2503.09516) | PPO/GRPO 强化学习训练模型在推理中自主发检索；提出 retrieved-token masking 稳定训练，7 个 QA 基准上较 RAG 基线提升约 41%（7B 模型） |
| **ReSearch** | NeurIPS 2025 | 无需监督推理数据的 GRPO 训练，检索查询融入推理链，涌现反思与自我纠错 |
| **R1-Searcher / DeepResearcher** | 2025 | 同一范式的扩展：多轮深度研究、网页浏览环境训练 |

研究侧之外，工程侧的落地载体是 LangGraph（编排）+ 检索工具（MCP Server）+ 轨迹可观测（Langfuse/LangSmith）的组合。

## 框架选型对比

| 维度 | LangChain/LangGraph | LlamaIndex | Haystack | RAGFlow/Dify/FastGPT |
|---|---|---|---|---|
| 上手速度 | 快 | 中 | 中 | 很快 |
| RAG 抽象自然度 | 中 | 高 | 高 | 高（可视化） |
| Agentic 编排能力 | 强（LangGraph） | 中（Workflows） | 弱 | 中（Dify Workflow） |
| 企业可扩展性 | 中 | 中 | 中高 | 中 |
| 生态/集成 | 最广 | 广 | 中 | 依赖产品 |
| 适合场景 | 通用 Agent + RAG | 数据密集型 RAG | 企业流水线 | 快速原型/业务平台 |

## 小结

没有“最好”的框架，只有“最适合当前阶段”的组合。原型阶段用 LlamaIndex 或 Dify 快速验证；Agentic 检索用 LangGraph 编排 + MCP 工具化检索；图谱推理在确认多跳需求后再上 LightRAG/HippoRAG；生产阶段通常需要基于向量库 + 自研 Query Engine 来获得可控的延迟、成本与治理。
