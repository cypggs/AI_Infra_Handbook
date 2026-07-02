# Multi-Agent 总览

> 一句话理解：**Multi-Agent 是把一个复杂任务拆给多个具有不同角色、技能与视角的 Agent，通过消息传递、协作编排与共享状态，共同完成单 Agent 难以做好的事**。

## 本主题适合谁

- 正在设计多角色 AI 系统（客服、研发助手、研究 Agent）的工程师。
- 发现单 Agent 在复杂任务里容易“既要规划、又要执行、还要记忆”导致能力边界模糊的开发者。
- 关心 Agent 之间如何分工、通信、同步、冲突解决的架构师。
- 准备 AI Infra 面试的候选人。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么复杂任务需要从单 Agent 走向 Multi-Agent。
2. 说明 Multi-Agent 的核心抽象：角色、技能、消息总线、协调器、共享黑板、观察者。
3. 画出 Multi-Agent 分层架构，并区分控制面与数据面。
4. 对比 Manager-Worker、Peer-to-Peer、Pipeline、Auction、Handoff 等协作模式。
5. 理解 Agent Registry、Message Bus、Coordinator、Blackboard、Observer 等核心模块的职责。
6. 对比 AutoGen、LangGraph multi-agent、CrewAI、OpenAI Agents SDK handoffs、CAMEL、MetaGPT 的设计取舍。
7. 知道生产环境中 Multi-Agent 的部署、并发、持久化、隔离、可观测与失败恢复要点。
8. 回答 Multi-Agent 选型、协作模式、冲突解决、可观测等面试问题。

## Multi-Agent 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Multi-Agent 的关系 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | 单 Agent 如何安全、可观测地执行 | Multi-Agent 中的每个 Agent 都运行在 Runtime 之上；Runtime 提供 ReAct、工具、护栏等原子能力 |
| [Agent Memory](/05-agent/memory/) | 如何保留并利用上下文与经验 | Multi-Agent 共享或隔离的长期记忆是协作基础；Blackboard 也需要 Memory 做持久化 |
| **Multi-Agent** | 多个 Agent 如何分工协作完成复杂目标 | 承上启下，把单 Agent 能力编排成群体智能 |
| Planning（后续主题） | 如何分解与重规划任务 | Coordinator 依赖 Planner 做任务拆分与再分配 |
| MCP（后续主题） | 工具发现与调用协议 | Agent 可通过 MCP 发现彼此能力，但 Multi-Agent 协作不依赖 MCP |
| RAG（后续主题） | 外部知识检索 | 多个 Agent 可共享 RAG 检索结果，Blackboard 中沉淀共同上下文 |

上表可以概括为一句话：**Agent Runtime 决定“单个 Agent 怎么执行”，Multi-Agent 决定“多个 Agent 怎么协作”，Memory 决定“它们记得什么、共享什么”**。

## 本章结构

1. [背景](01-background) — 单 Agent 的局限、Multi-Agent 演进阶段、典型场景、核心挑战。
2. [核心思想](02-core-ideas) — 角色、技能、消息总线、协调器、黑板、Handoff、共识、观测、失败恢复。
3. [架构设计](03-architecture) — 分层架构、控制面/数据面、部署形态、与 Runtime/Memory 集成。
4. [协作模式](04-collaboration-patterns) — Manager-Worker、Peer-to-Peer、Pipeline、Auction、动态 Handoff 与生命周期。
5. [核心模块](05-core-modules) — Agent Registry、Role & Skill、Message Bus、Coordinator、Blackboard、Observer、终止与冲突解决。
6. [源码分析](06-source-analysis) — AutoGen、LangGraph multi-agent、CrewAI、OpenAI Agents SDK handoffs、CAMEL、MetaGPT。
7. [工程实践](07-mini-demo) — 纯 Python Mini Demo 设计与运行说明。
8. [企业生产实践](08-production-practice) — 部署拓扑、并发、持久化、消息队列、权限隔离、成本、HITL、失败恢复。
9. [最佳实践](09-best-practices) — 角色设计、消息契约、避免过度协调、冲突解决、可观测优先、版本管理、评测、渐进落地。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、论文、工程文章、学习路径。

## 一句话总结

Multi-Agent 不是简单地“多跑几个 Agent”，而是**通过清晰的角色边界、可靠的消息机制、统一的协调策略和可观测的共享状态，把多个单 Agent 的能力有序组合成群体智能**。

## 本章小结

Multi-Agent 是 Agent 基础设施的上一层编排：它依赖 Agent Runtime 提供单 Agent 执行能力，依赖 Agent Memory 提供共享或隔离的记忆，依赖 Planning 做任务拆分，依赖 MCP/RAG 扩展知识与工具。核心目标是让多个 Agent 在复杂任务中各司其职、协同演进。

**参考来源**

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [CAMEL Documentation](https://docs.camel-ai.org/)
- [MetaGPT Documentation](https://docs.deepwisdom.ai/main/Main%20Guide/)
