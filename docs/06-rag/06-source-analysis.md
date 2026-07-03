# 源码与生态分析

RAG 生态已经高度繁荣。本章选取最具代表性的框架、向量库和模型，分析它们的设计取舍，帮助你在选型时做出理性判断。

## LangChain

- **定位**：LLM 应用编排框架，RAG 只是其众多用例之一。
- **核心抽象**：`DocumentLoader`、`TextSplitter`、`Embeddings`、`VectorStore`、`Retriever`、`Runnable` 接口。
- **RAG 模式**：`create_retrieval_chain`、`ConversationalRetrievalChain`、`MultiQueryRetriever`、`ContextualCompressionRetriever`。
- **优点**：生态最全、上手快、文档丰富。
- **缺点**：抽象层级多，生产调试复杂；版本迭代快，API 兼容性需要关注。

## LlamaIndex

- **定位**：以 RAG 和数据为中心的 LLM 应用框架。
- **核心抽象**：`Node`（chunk）、`Index`、`Retriever`、`QueryEngine`、`ResponseSynthesizer`。
- **RAG 模式**：
  - `VectorStoreIndex` + `as_query_engine()`。
  - `SubQuestionQueryEngine` 自动分解复杂查询。
  - `RouterQueryEngine` 按查询选择不同索引/工具。
- **优点**：RAG 场景抽象更自然，支持高级检索（递归、摘要、图）。
- **缺点**：学习曲线略陡，部分高级功能绑定 LlamaIndex 生态。

## Haystack

- **定位**：面向企业的 NLP/RAG Pipeline 框架，强调流水线组件化。
- **核心抽象**：`Component`、`Pipeline`、`DocumentStore`、`Retriever`、`Reader`/`Generator`。
- **RAG 模式**：
  - `Pipeline` 用 YAML/代码定义：Preprocess → Embed → Retrieve → Rerank → Generate。
  - 支持多种 DocumentStore（OpenSearch、Pinecone、Weaviate、Qdrant、Milvus）。
- **优点**：流水线可视化、企业级集成友好。
- **缺点**：社区活跃度相对 LangChain/LlamaIndex 较低。

## RAGFlow / Dify / Flowise

| 产品 | 定位 | 特点 |
|---|---|---|
| **RAGFlow** | 开源深度文档 RAG 引擎 | 强调高质量文档解析、可解释召回、模板化 Agent |
| **Dify** | LLM 应用开发平台 | 可视化编排、知识库、Agent、Workflow、Prompt 管理 |
| **Flowise** | 低代码 LLM 工作流 | 拖拽节点构建 RAG 流水线，适合原型 |

这些工具适合快速搭建与业务迭代，但在大规模、多租户、强治理场景下通常需要二次开发或自建核心链路。

## 向量数据库与索引库

| 产品 | 类型 | 特点 |
|---|---|---|
| **Milvus/Zilliz** | 分布式向量数据库 | 云原生、分片、多副本、强一致性 |
| **Pinecone** | 托管向量数据库 | 免运维、metadata 过滤、hybrid search |
| **Weaviate** | 向量+语义数据库 | GraphQL 接口、模块化、本地/云 |
| **Qdrant** | 向量数据库 | Rust 实现、过滤性能强、自托管友好 |
| **Chroma** | 嵌入式向量库 | 本地开发友好，不适合大规模生产 |
| **pgvector** | Postgres 扩展 | 与 SQL 生态集成，适合已有 PG 的团队 |
| **Faiss** | 索引库 | 高性能 ANN，需自管存储与分布式 |
| **Elasticsearch/OpenSearch** | 搜索引擎 | 混合检索成熟，BM25 + dense 结合方便 |

## Embedding 与 Reranker 模型

| 模型 | 类型 | 说明 |
|---|---|---|
| OpenAI text-embedding-3 | Dense | 综合能力强，API 调用方便 |
| BGE / BGE-M3 | Dense/Sparse | 中文/多语言表现好，支持多模态/长文本 |
| E5 | Dense | Microsoft 开源，通用检索强 |
| Jina Embeddings | Dense | 长上下文、多语言 |
| GTE | Dense | Alibaba 开源，中文场景优秀 |
| Cohere Rerank | Reranker | API 版 cross-encoder，精度高 |
| BGE-Reranker | Reranker | 开源可部署，性价比好 |
| ColBERT | Late Interaction | 精度高、延迟高，适合高价值检索 |

## GraphRAG

GraphRAG 在向量检索之上引入知识图谱：

- **索引阶段**：从文档抽取实体与关系，构建图谱，同时保留文本 chunk 的向量索引。
- **查询阶段**：可以先在图谱上做社区发现/子图检索，再映射到相关文本；或把子图作为上下文。
- **代表实现**：Microsoft GraphRAG、Neo4j + vector、LlamaIndex PropertyGraphIndex。
- **适用**：需要跨文档推理、关系复杂、实体众多的场景。

## 框架选型对比

| 维度 | LangChain | LlamaIndex | Haystack | RAGFlow/Dify |
|---|---|---|---|---|
| 上手速度 | 快 | 中 | 中 | 很快 |
| RAG 抽象自然度 | 中 | 高 | 高 | 高（可视化） |
| 企业可扩展性 | 中 | 中 | 中高 | 中 |
| 生态/集成 | 最广 | 广 | 中 | 依赖产品 |
| 适合场景 | 通用 Agent | 数据密集型 RAG | 企业流水线 | 快速原型/业务平台 |

## 小结

没有“最好”的框架，只有“最适合当前阶段”的组合。原型阶段用 LlamaIndex 或 Dify 快速验证；生产阶段通常需要基于向量库 + 自研 Query Engine 来获得可控的延迟、成本与治理。
