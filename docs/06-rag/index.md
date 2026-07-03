# RAG 篇

RAG（Retrieval-Augmented Generation，检索增强生成）通过在生成前引入外部知识检索，解决大语言模型在事实性、时效性、私域知识上的不足。它把“记忆”从模型参数中解耦出来，变成可独立迭代、可审计、可治理的数据系统。

## 一句话理解

> RAG 让大模型在回答之前先查资料，基础设施要让“查到的资料”足够准、足够快、足够可控。

## 学习目标

读完本主题后，你应该能够：

- 拆解端到端 RAG 流水线，并说明每一步的关键权衡。
- 根据业务场景选择 chunking、embedding、retrieval、reranking 的组合。
- 设计可水平扩展、可实时更新、可观测的 RAG 服务架构。
- 在 Agent 系统中把 Retriever 作为工具或 MCP Server 集成。
- 建立 RAG 系统的评估、迭代与生产运维闭环。

## 与相邻主题的关系

RAG 不是孤立的“向量搜索”，它需要与 LLM 服务、Agent 运行时、记忆系统、工具协议紧密协作。

| 相邻主题 | 与 RAG 的关系 |
|---|---|
| [LLM Gateway](/04-llmops/llm-gateway/) | 统一路由生成请求、限流、兜底模型、缓存 token 成本，是 RAG 在线服务的流量入口。 |
| [Agent Runtime](/05-agent/agent-runtime/) | Agent 循环可以把 Retriever 当作工具调用，RAG 是其获取外部知识的主要方式。 |
| [Memory](/05-agent/memory/) | 长期语义记忆通常以向量存储为载体，RAG 检索可视为记忆读取的一种实现。 |
| [MCP](/05-agent/mcp/) | Retriever、知识库、文档工具可作为 MCP Server 被任何兼容 Host 调用。 |
| [Planning](/05-agent/planning/) | 复杂查询需要先分解再多次检索，Planning 模块决定检索顺序与迭代策略。 |
| [Tool Use](/05-agent/tool-use/) | 检索器本质上是一个“返回文档片段”的工具，需要 Schema、调用、格式化与可观测。 |
| [Agent OS](/05-agent/agent-os/) | Agent OS 为 RAG 检索任务提供进程隔离、资源调度与沙箱执行环境。 |

## 章节导航

1. [背景：为什么需要 RAG](/06-rag/01-background) — 从 Prompt Engineering 到 Fine-tuning 再到 RAG 的演进，以及 RAG 与长上下文、持续预训练的关系。
2. [核心概念](/06-rag/02-core-ideas) — 数据流水线、chunking、embedding、检索策略、reranking、生成增强与评估指标。
3. [架构设计](/06-rag/03-architecture) — 端到端 RAG 系统架构，数据平面与控制平面，离线索引与在线服务。
4. [RAG 流水线](/06-rag/04-rag-pipeline) — 查询预处理、检索、重排、上下文组装、生成与后处理的状态机。
5. [核心模块](/06-rag/05-core-modules) — Document Loader、Chunker、Embedder、Vector Store、Retriever、Reranker、Query Engine、Generator、Memory/Cache、Evaluator、Observer。
6. [源码与生态分析](/06-rag/06-source-analysis) — LangChain、LlamaIndex、Haystack、RAGFlow/Dify、向量库、Embedding/Reranker 模型、GraphRAG 实现对比。
7. [Mini Demo](/06-rag/07-mini-demo) — 本主题配套示例说明：目录结构、运行方式、关键代码与生产差异。
8. [企业生产实践](/06-rag/08-production-practice) — 大规模索引、实时更新、多租户、PII 与权限、缓存、成本延迟、可观测、故障模式。
9. [最佳实践](/06-rag/09-best-practices) — chunking、检索、重排、提示、评估与迭代的检查清单和反模式。
10. [面试题](/06-rag/10-interview-questions) — 覆盖初级、中级、高级工程师的面试问题。
11. [延伸阅读](/06-rag/11-further-reading) — 论文、官方文档、博客、交叉引用与学习路径。

## 一句话总结

RAG 是把“知识”从模型参数搬到可管理的外部存储，再通过高质量检索将其注入生成过程；其基础设施的核心是索引质量、检索精度、生成可控性与全链路可观测。
