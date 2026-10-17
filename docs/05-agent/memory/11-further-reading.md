# 11. 延伸阅读

## 官方文档（必读）

- [Letta Documentation](https://docs.letta.com)
  - 前身 MemGPT 的后续项目，学习 Core / Recall / Archival Memory 的分层设计。
- [Letta GitHub](https://github.com/letta-ai/letta)
  - 开源实现，重点看 memory 模块与 agent loop 的交互。
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  - 生产级状态持久化，重点看 checkpoint、thread、中断恢复。
- [LangGraph Add Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
  - 跨会话长期记忆的 Store 机制。
- [OpenAI Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)
  - OpenAI 生态的会话与记忆管理。
- [Mem0 Documentation](https://docs.mem0.ai)
  - 面向 AI 助手的记忆层，重点看 user/session/memory 抽象。
- [Graphiti GitHub（Zep 开源引擎）](https://github.com/getzep/graphiti)
  - 时序知识图谱记忆引擎，重点看双时序模型、episode/entity/community 子图与 MCP Server。
- [MemOS GitHub（MemTensor）](https://github.com/MemTensor/MemOS)
  - “记忆操作系统”实现，重点看 MemCube 抽象与 MemScheduler。
- [LangMem GitHub](https://github.com/langchain-ai/langmem)
  - LangGraph 生态的原生记忆 SDK，扁平 KV + 向量记忆与 prompt 优化。

## 向量数据库文档

- [Chroma Documentation](https://docs.trychroma.com)
  - 轻量向量数据库，适合原型与本地开发。
- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
  - 云原生向量数据库，支持模块化 pipeline 与 hybrid search。
- [Milvus Documentation](https://milvus.io/docs)
  - 面向大规模向量检索的数据库，重点看索引类型与分布式部署。
- [pgvector GitHub](https://github.com/pgvector/pgvector)
  - PostgreSQL 向量扩展，适合已有 Postgres 基础设施的团队。

## 论文

- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
  - Agent 分层记忆的奠基论文，必读。
- [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110)
  - 2025 年代表性记忆架构：原子化 note、自动建立 note 间链接、记忆随时间演化，在 LoCoMo 基准上对比 MemGPT、MemoryBank 等基线。
- [Sleep-time Compute: Beyond Inference Scaling at Test-time](https://arxiv.org/abs/2504.13171)
  - Letta / UC Berkeley 提出“睡眠时计算”，把记忆整理移出请求路径，约 5 倍降低测试时计算量。
- [MemOS: An Operating System for Memory-Augmented Generation](https://arxiv.org/abs/2505.22101)
  - “记忆操作系统”：MemCube 统一封装参数/激活/明文记忆，配 MemScheduler、MemLifecycle 等 OS 式组件。
- [Zep: A Temporal Knowledge Graph Architecture for Agent Memory（Rasmussen et al., 2025）](https://arxiv.org/abs/2501.13956)
  - 双时序知识图谱记忆引擎的技术报告，理解 episode/entity/community 三层子图与混合检索。
- [LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory](https://arxiv.org/abs/2410.10819)
  - 长期交互记忆基准，覆盖时序推理、知识更新与拒答。
- [LoCoMo: Evaluating Very Long-Term Conversational Memory](https://arxiv.org/abs/2402.17753)
  - 超长多会话对话记忆基准，目前社区使用最广，也伴随厂商评测争议。
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)
  - 长上下文不等于好记忆的经典证据，理解为什么外部记忆仍然必要。
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
  - Agent Runtime 的基础范式，理解 Runtime 如何调用 Memory。
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
  - RAG 基础论文，帮助区分 Memory 与 RAG。

## 工程文章

- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
  - 系统梳理 Agent 记忆分类与设计权衡。
- [LangGraph Memory Store Guide](https://docs.langchain.com/oss/python/langgraph/add-memory)
  - 跨会话记忆的工程实践。
- [Mem0 Blog / Guides](https://docs.mem0.ai)
  - 用户-centric 记忆层的实现思路。

## 相关主题

- [Agent Runtime 详解](/05-agent/agent-runtime/) — Memory 的调用方，理解 ReAct 循环中的记忆读写。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — Agent Runtime 通常通过 Gateway 调用模型，记忆系统也可通过 Gateway 调用 embedding 模型。
- [vLLM 详解](/04-llmops/vllm/) — 可作为 Agent Runtime 的上游推理引擎。
- [RAG 主题](/05-agent/)（后续主题）— 外部知识检索，与 Memory 同源但数据不同。
- [Planning 详解](/05-agent/planning/) — Planner 可以利用 Episodic Memory 中的经验生成更优计划。
- [Tool Use 详解](/05-agent/tool-use/) — 工具调用层；工具结果与偏好可写入 Memory。
- [Agent OS 详解](/05-agent/agent-os/) — Agent OS 管理进程级 Workspace 与状态，Memory 提供跨进程持久化与检索。
- [Personal AI Agent 详解](/05-agent/personal-agent/) — 个人智能体的记忆分层与个人知识图谱是 Memory 的 C 端产品化形态。
- [Multi-Agent 主题](/05-agent/multi-agent/) — 共享或隔离的长期记忆池是多 Agent 协作的基础。
- [Reflection 主题](/05-agent/reflection/) — Reflection 系统产出 critique、score 与改进经验，是 Episodic Memory 的重要输入。
- [MCP 主题](/05-agent/mcp/) — Memory 可以暴露 `remember/recall` 接口供 Runtime 通过 [MCP](/05-agent/mcp/) 调用。

## 推荐学习路径

1. 先读 MemGPT 论文，理解 Core / Recall / Archival Memory 的分层思想。
2. 阅读 Steve Kinney 的文章，建立记忆分类与生命周期的系统认知。
3. 用 Letta 或 Mem0 跑一个带长期记忆的对话 Agent，观察记忆如何影响回答。
4. 阅读本主题的 [Mini Demo](./07-mini-demo)，理解零外部依赖下的记忆机制实现。
5. 结合 [生产实践](./08-production-practice) 与 [最佳实践](./09-best-practices)，思考多租户、隐私、embedding 版本管理与评测落地。
6. 如果已读过 [Agent Runtime](/05-agent/agent-runtime/)，重点对比 Runtime 与 Memory 的边界与协作方式。

## 本章小结

Agent Memory 的延伸阅读覆盖了官方文档、论文、工程文章与相关主题。MemGPT 论文奠定了分层记忆的理论基础；Letta、LangGraph、Mem0 代表了不同的工程实现取向；Chroma、Weaviate、Milvus、pgvector 提供了多样化的向量存储选择。结合本主题的 [Mini Demo](./07-mini-demo)、[生产实践](./08-production-practice) 与 [最佳实践](./09-best-practices)，可以从理论到工程全面掌握 Agent Memory。

**参考来源**

- [Letta Docs](https://docs.letta.com)
- [Letta GitHub](https://github.com/letta-ai/letta)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Add Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [OpenAI Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [Mem0 Docs](https://docs.mem0.ai)
- [Chroma Docs](https://docs.trychroma.com)
- [Weaviate Docs](https://weaviate.io/developers/weaviate)
- [Milvus Docs](https://milvus.io/docs)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [MemGPT Paper](https://arxiv.org/abs/2310.08560)
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
