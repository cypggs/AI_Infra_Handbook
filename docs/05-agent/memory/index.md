# Agent Memory 总览

> 一句话理解：**Agent Memory 是 Agent 的“记忆系统”**，负责在多次交互中感知、编码、存储、检索、回注和遗忘信息，让 Agent 从“一轮问答”进化成“持续学习、长期服务”的助手。

## 本主题适合谁

- 正在设计或实现 Agent 系统的工程师，希望理解记忆层应该如何与 Runtime 配合。
- 对 RAG 已有了解，但希望区分“外部知识检索”与“Agent 自身经验积累”的开发者。
- 负责多轮对话、个性化助手、长期任务等场景的产品与架构师。
- 准备 AI Infra 相关面试的候选人。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么 Agent 需要独立于 Prompt 和 RAG 的记忆系统。
2. 区分工作记忆、短期记忆、长期记忆、语义记忆、情景记忆与程序性记忆。
3. 描述记忆从感知到遗忘的完整生命周期。
4. 画出 Agent Memory 的分层架构，并说明与 Agent Runtime、RAG、MCP 的边界。
5. 理解 embedding、向量检索、摘要压缩、TTL、隐私过滤等核心机制。
6. 对比 Letta（MemGPT）、LangGraph Persistence/Store、OpenAI Agents SDK Sessions、Mem0 等主流实现。
7. 知道如何为自己的 Agent 选择存储后端、embedding 模型与检索策略。
8. 跑通并扩展本主题的 Mini Demo，理解多层记忆的写入与检索。
9. 回答关于记忆分类、向量检索、长期记忆与 RAG 区别、多租户隔离等面试问题。

## Agent Memory 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Agent Memory 的关系 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | 如何安全、可观测地执行 Agent 任务 | Runtime 在 ReAct 循环中读写 Memory；Memory 为 Runtime 提供上下文与经验 |
| **Agent Memory** | 如何保留并利用 Agent 运行中产生的上下文与经验 | 承上启下，把“瞬时对话”转化为“可持续积累的记忆” |
| RAG（后续主题） | 如何从外部知识库检索固定知识 | RAG 读的是企业知识库；Memory 读的是 Agent 自身运行中积累的用户偏好、任务经验 |
| Planning（后续主题） | 如何分解与重规划任务 | Planner 可以利用 Episodic Memory 中的成功案例来生成更优计划 |
| [MCP](/05-agent/mcp/) | 工具发现与调用协议 | Memory 可以暴露 `remember/recall` 接口供 Runtime 通过 function call 调用；[MCP](/05-agent/mcp/) 是可选协议 |
| [Multi-Agent](/05-agent/multi-agent/) | 多 Agent 协作 | 共享或隔离的长期记忆池是多 Agent 协作的基础；Memory 为 Multi-Agent 提供跨 Agent 上下文 |

上表可以概括为一句话：**Agent Runtime 决定“怎么执行”，RAG 决定“读什么外部知识”，Memory 决定“记住什么、忘记什么、回注什么”**。

## 本章结构

1. [背景](01-background) — 从“无状态 LLM → 上下文历史 → 长期记忆”的演进，Memory 与 RAG、Cache、Agent Runtime 的区别。
2. [核心思想](02-core-ideas) — 记忆分类、记忆层次、生命周期、检索策略、遗忘与摘要、个性化、隐私。
3. [架构设计](03-architecture) — Agent Runtime → Memory Service → 多层 Memory → Embedder → Vector Store → Storage 的分层架构。
4. [记忆生命周期](04-memory-lifecycle) — Perceive → Encode → Store → Index → Retrieve → Inject → Forget/Decay/Update 完整流程。
5. [核心模块](05-core-modules) — Working Memory、Short-term Memory、Long-term Memory、Episodic Memory、Embedder、Vector Store、Retriever、Summarizer、Storage Backend、Memory Service、Privacy Filter。
6. [源码分析](06-source-analysis) — Letta（MemGPT）、LangGraph persistence/store、OpenAI Agents SDK Sessions、Mem0、向量数据库设计取舍。
7. [工程实践](07-mini-demo) — 纯 Python、零外部依赖的 Mini Demo 设计与运行说明。
8. [企业生产实践](08-production-practice) — 多租户隔离、向量 DB 选型、embedding 模型管理、隐私/TTL、与 Runtime 集成、可观测。
9. [最佳实践](09-best-practices) — 按记忆类型选存储、上下文长度控制、避免记忆污染、embedding 版本管理、敏感信息过滤、评测。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、论文、工程文章、向量数据库文档。

## 一句话总结

Agent Memory 不是给 Prompt 塞更多历史记录，而是**把 Agent 运行过程中产生的上下文、事实、偏好与经验结构化地保存下来，并在合适的时机以合适的形式回注到 Runtime**，从而让 Agent 在多轮、多会话、多任务中持续变聪明。

## 本章小结

Agent Memory 是 Agent 基础设施中承上启下的一层：它向上为 Agent Runtime 提供可检索、可遗忘、可个性化的上下文，向下管理 embedding、向量检索、存储后端与生命周期。它与 RAG、Cache、Agent Runtime 有清晰边界，核心目标是让 Agent 具备持续积累与复用经验的能力。

**参考来源**

- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- [Letta Documentation](https://docs.letta.com)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
