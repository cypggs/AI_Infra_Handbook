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

## 推荐学习路径

1. **入门**：读 RAG 奠基论文，用 LangChain/LlamaIndex 跑通一个 PDF 问答 Demo。
2. **进阶**：评估 dense/sparse/hybrid 检索，加入 reranker，建立 RAGAS 评估集。
3. **深入**：阅读 ColBERT/SPLADE/GraphRAG，理解高级检索与推理增强。
4. **生产**：设计多租户、增量更新、缓存、可观测与反馈闭环的 RAG 服务。

## 一句话收尾

RAG 是连接“静态知识库”与“动态语言模型”的桥梁；桥梁的承载力取决于索引质量、检索精度、生成可控性与持续迭代机制。
