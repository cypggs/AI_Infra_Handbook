# 延伸阅读

本章列出 RAG 相关的论文、官方文档、博客与学习路径，并给出相邻主题的交叉引用。

## 学术论文

- **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks**
  - 论文地址：https://arxiv.org/abs/2005.11401
  - 价值：RAG 的奠基论文，理解“先检索再生成”的范式。

- **Dense Passage Retrieval for Open-Domain QA**
  - 论文地址：https://arxiv.org/abs/2004.04906
  - 价值：DPR 双塔检索，现代 dense retrieval 的基础。

- **BGE: BAAI General Embedding**
  - 论文/模型：https://github.com/FlagOpen/FlagEmbedding
  - 价值：中文/多语言开源 embedding 的优秀基线。

- **SPLADE: Sparse Lexical and Expansion Model**
  - 论文地址：https://arxiv.org/abs/2107.05720
  - 价值：学习得到的稀疏表示，连接 BM25 与 dense retrieval。

- **ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction**
  - 论文地址：https://arxiv.org/abs/2004.12832
  - 价值：token 级 late interaction，检索精度高。

- **Reciprocal Rank Fusion outperforms BM25**
  - 论文地址：https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
  - 价值：RRF 的经典说明。

- **RAGAS: Automated Evaluation of Retrieval Augmented Generation**
  - 项目地址：https://github.com/explodinggradients/ragas
  - 价值：端到端 RAG 评估框架。

- **GraphRAG**
  - 论文/项目：https://github.com/microsoft/graphrag
  - 价值：知识图谱增强 RAG。

## 2025–2026 新进展

- **LaRA: Benchmarking Retrieval-Augmented Generation and Long-Context LLMs — No Silver Bullet**
  - 论文地址：https://arxiv.org/abs/2502.09977 （ICML 2025）
  - 价值：长上下文 vs RAG 论战的关键基准——比较/推理智取 RAG，幻觉抑制与拒答 RAG 更稳。

- **NoLiMa: Long-Context Evaluation Beyond Literal Matching**
  - 论文地址：https://arxiv.org/abs/2502.05167 （ICML 2025）
  - 价值：揭示标称 128K 上下文的模型多数在 32K 内严重衰减，反驳“长上下文取代 RAG”。

- **Search-R1: Training LLMs to Reason and Leverage Search Engines with Reinforcement Learning**
  - 论文地址：https://arxiv.org/abs/2503.09516
  - 价值：RL 训练模型在推理中自主检索的开山之作，Agentic 检索范式的代表。

- **ReSearch: Learning to Reason with Search for LLMs via Reinforcement Learning**
  - 论文地址：https://arxiv.org/abs/2503.19470
  - 价值：无需监督推理数据的检索推理联合训练，涌现自我反思。

- **Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG**
  - 论文地址：https://arxiv.org/abs/2501.09136
  - 价值：Agentic RAG 模式（single-shot / router / iterative）的系统综述。

- **Contextual Retrieval（Anthropic）**
  - 博客地址：https://www.anthropic.com/news/contextual-retrieval
  - 价值：嵌入前注入文档级上下文，检索失败率 5.7% → 1.9% 的工程实践。

- **Late Chunking: Chunked Embeddings Are Designed to Fail**
  - 论文地址：https://arxiv.org/abs/2409.04701
  - 价值：先整篇嵌入再切分，解决 chunk 脱离语境问题。

- **Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models**
  - 论文地址：https://arxiv.org/abs/2506.05176
  - 价值：2025 年开源 Embedding/Reranker 新基线，32K 上下文，登顶 MTEB 多语言榜。

- **ColPali: Efficient Document Retrieval with Vision Language Models**
  - 论文地址：https://arxiv.org/abs/2407.01449 （ICLR 2025）
  - 价值：视觉文档检索（多向量 + MaxSim），多模态 RAG 的标志性工作。

- **LightRAG: Simple and Fast Retrieval-Augmented Generation**
  - 项目地址：https://github.com/HKUDS/LightRAG
  - 价值：轻量化 GraphRAG，双层检索、更新友好，EMNLP 2025。

- **CRAG: Corrective Retrieval Augmented Generation**
  - 论文地址：https://arxiv.org/abs/2401.15884
  - 价值：检索质量自检与修正循环，工程落地门槛低。

- **RAGBench: Explainable Benchmark for Retrieval-Augmented Generation Systems**
  - 论文地址：https://arxiv.org/abs/2407.11005
  - 价值：行业级端到端基准与 TRACe 归因框架。

## 官方文档与框架

- **LangChain RAG 文档**
  - https://python.langchain.com/docs/tutorials/rag/

- **LlamaIndex RAG 文档**
  - https://docs.llamaindex.ai/en/stable/understanding/rag/

- **Haystack Pipelines**
  - https://docs.haystack.deepset.ai/docs/intro

- **Milvus 文档**
  - https://milvus.io/docs

- **Pinecone 文档**
  - https://docs.pinecone.io/

- **Qdrant 文档**
  - https://qdrant.tech/documentation/

- **OpenAI Embeddings**
  - https://platform.openai.com/docs/guides/embeddings

- **Cohere Rerank**
  - https://docs.cohere.com/docs/rerank

## 工程博客与文章

- **LangChain: RAG from scratch**
  - https://blog.langchain.dev/retrieval/

- **Pinecone: RAG 101**
  - https://www.pinecone.io/learn/retrieval-augmented-generation/

- **Microsoft: GraphRAG**
  - https://microsoft.github.io/graphrag/

- **RAGFlow: From RAG to Context — A 2025 Year-End Review of RAG**
  - https://ragflow.io/blog/rag-review-2025-from-rag-to-context
  - 价值：2025 年 RAG 领域全景回顾，检索与长上下文融合趋势的一手总结。

- **Qdrant: Is RAG Dead? Why Long Context Windows Don't Replace RAG**
  - https://qdrant.tech/articles/rag-is-dead/
  - 价值：从成本、延迟、数据治理角度反驳“RAG 已死”。

## 相邻主题交叉引用

| 主题 | 链接 | 与本主题关系 |
|---|---|---|
| LLM Gateway | /04-llmops/llm-gateway/ | RAG 在线服务的流量入口与模型路由。 |
| Agent Runtime | /05-agent/agent-runtime/ | Agent 把 Retriever 当作工具调用。 |
| Memory | /05-agent/memory/ | 向量存储是长期语义记忆的载体。 |
| MCP | /05-agent/mcp/ | 把 Retriever 封装为 MCP Server。 |
| Planning | /05-agent/planning/ | 复杂查询需要先规划再多次检索。 |
| Tool Use | /05-agent/tool-use/ | 检索器是一种返回文档的工具。 |
| Agent OS | /05-agent/agent-os/ | 为 RAG 任务提供进程与资源隔离。 |
| AI SRE | /07-ai-sre/ | 为 RAG 服务提供可观测性、SLO 与事故响应保障。 |
| Benchmark + Evaluation | /07-ai-sre/benchmark-evaluation/ | RAG 流水线需要端到端评估：检索召回、生成事实性、延迟与成本。 |

## 推荐学习路径

1. **入门**：读 RAG 奠基论文，用 LangChain/LlamaIndex 跑通一个 PDF 问答 Demo。
2. **进阶**：评估 dense/sparse/hybrid 检索，加入 reranker，建立 RAGAS 评估集。
3. **深入**：阅读 ColBERT/SPLADE/GraphRAG，理解高级检索与推理增强。
4. **生产**：设计多租户、增量更新、缓存、可观测与反馈闭环的 RAG 服务。
5. **前沿（2025+）**：读 LaRA/NoLiMa 理解长上下文与 RAG 的边界，用 LangGraph + MCP 工具实现 Agentic 检索，读 Search-R1/ReSearch 理解 RL 检索训练范式。

## 一句话收尾

RAG 是连接“静态知识库”与“动态语言模型”的桥梁；2025 年之后，这座桥从固定车道变成了智能调度系统——模型自己决定何时上桥、走哪条路、何时掉头。桥梁的承载力仍取决于索引质量、检索精度、生成可控性与持续迭代机制。
