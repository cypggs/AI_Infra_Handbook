# Agent Reflection 总览

> 一句话理解：**Agent Reflection 是 Agent 的“自省系统”**，让 Agent 在生成结果后主动批判、评估、修订，从而把“一次性回答”进化成“持续优化的输出”。

## 本主题适合谁

- 正在设计或实现 Agent 系统的工程师，希望理解反思层如何与 Runtime、Memory、Multi-Agent 配合。
- 发现单轮 LLM 或 ReAct 在复杂任务中仍然出错的开发者。
- 负责代码生成、内容创作、规划决策、工具调用等高要求场景的架构师。
- 准备 AI Infra 相关面试的候选人。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释为什么单轮 LLM 和 ReAct 仍然需要独立的 Reflection 机制。
2. 说明 Reflection 的核心思想：生成、批判、评估、修订的闭环。
3. 区分内部反馈与外部反馈、行动反思与计划反思、个体反思与群体反思。
4. 画出 Agent Reflection 的分层架构，并说明与 Generator、Critic、Evaluator、Revision Controller 的关系。
5. 描述 Reflection Loop 的完整状态流转与终止条件。
6. 对比 Self-Refine、Reflexion、CRITIC、Tree of Thoughts、LangGraph Reflection、AutoGen Reflection、OpenAI o1 的设计取舍。
7. 知道如何为自己的 Agent 选择 Critic 模型、评分标准、终止策略与人工兜底方案。
8. 理解 Mini Demo 的设计与运行方式，能在本地复现“生成—批判—修订”过程。
9. 回答关于 Reflection 与 ReAct 区别、Critic 设计、避免无限循环、与 Memory 集成等面试问题。

## Agent Reflection 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Agent Reflection 的关系 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | 如何安全、可观测地执行 Agent 任务 | Runtime 提供 ReAct 循环与工具执行环境，Reflection 在此基础上叠加“生成—批判—修订”闭环 |
| [Agent Memory](/05-agent/memory/) | 如何保留并利用上下文与经验 | Reflection 产生的 critique、score、revision 可以写入 Memory，形成可复用的经验教训 |
| **Agent Reflection** | 如何让 Agent 主动发现并修正自身错误 | 承上启下，把“即时生成”转化为“迭代优化” |
| [Multi-Agent](/05-agent/multi-agent/) | 多 Agent 如何分工协作 | 群体反思（Group Reflection）依赖 Multi-Agent 的通信与协调机制 |
| [Planning](/05-agent/planning/) | 如何分解与重规划任务 | Plan Reflection 在规划层面做批判与重规划，是 Reflection 与 Planning 的交汇点 |
| [Tool Use](/05-agent/tool-use/) | 工具调用与执行 | Tool-use Reflection 专门反思工具选择、参数填充与调用结果 |
| [Agent OS](/05-agent/agent-os/) | 运行时操作系统 | Reflection 结果可触发 Agent OS 的 checkpoint/rollback 或流程升级 |
| [MCP](/05-agent/mcp/) | 工具发现与调用协议 | Reflection 可以调用外部验证工具（如编译器、单元测试、检索）获取客观反馈；[MCP](/05-agent/mcp/) 提供标准化工具发现 |
| RAG | /06-rag/ | Reflection 可基于 RAG 检索结果评估答案忠实度。 |
| AI SRE | /07-ai-sre/ | AI SRE 为 Reflection 质量评估提供数据与告警。 |

上表可以概括为一句话：**Agent Runtime 决定“怎么执行”，Memory 决定“记住什么”，Reflection 决定“怎么发现错误并改得更好”**。

## 本章结构

1. [背景](01-background) — 单轮 LLM 与 ReAct 的局限、人类元认知启发、Reflection 演进阶段、典型场景。
2. [核心思想](02-core-ideas) — 生成 + 批判 + 评估 + 修订、内部/外部反馈、行动/计划反思、个体/群体反思、与 Memory 集成。
3. [架构设计](03-architecture) — Generator / Critic / Evaluator / Revision Controller / Workspace / Reflection Memory / Policy / Observer / Human Gate。
4. [反思循环](04-reflection-loop) — generate → critique → score → revise → terminate，状态与序列图、终止条件、护栏、HITL。
5. [核心模块](05-core-modules) — 各模块职责、输入输出、关键接口、生产注意事项。
6. [源码分析](06-source-analysis) — Self-Refine、Reflexion、CRITIC、Tree of Thoughts、LangGraph Reflection、AutoGen Reflection、OpenAI o1 / reasoning models。
7. [工程实践](07-mini-demo) — 纯 Python Mini Demo 设计与运行说明。
8. [企业生产实践](08-production-practice) — 何时启用 Reflection、Critic 模型选择、评分校准、在线/离线反思、与 Runtime/Memory 集成、评测基准。
9. [最佳实践](09-best-practices) — criteria-first、聚焦 Critic、避免无限循环、人工兜底、持久化反思结果、策略版本管理。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、论文、工程文章、相关主题、学习路径。

## 一句话总结

Agent Reflection 不是让 LLM 多生成几轮，而是**让 Agent 在生成后主动批判自身输出、量化质量、定向修订，并把反思过程与结果沉淀为可复用的经验**，从而在代码、写作、规划、工具使用等复杂任务中持续逼近正确解。

## 本章小结

Agent Reflection 是 Agent 基础设施中负责“自我纠错”的一层：它向上为 Agent Runtime 提供生成—批判—评估—修订的闭环能力，向下依赖 Memory 保存反思经验、依赖 Multi-Agent 实现群体反思、依赖外部工具获取客观反馈。它与 Runtime、Memory、Planning、Multi-Agent、Tool Use、MCP 都有清晰边界，核心目标是让 Agent 从“一次性回答”进化为“迭代优化”。

**参考来源**

- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [Reflexion: Self-Reflective Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [LangGraph Reflection Tutorial](https://langchain-ai.github.io/langgraph/tutorials/reflection/reflection/)
- [AutoGen Reflection](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/reflection.html)
- [OpenAI o1 / Reasoning Models](https://openai.com/index/learning-to-reason-with-llms/)
- [LangGraph Blog — Reflection Agents](https://blog.langchain.dev/reflection-agents/)
