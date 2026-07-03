# Agent Planning 总览

> 一句话理解：**Agent Planning 是 Agent 的“任务拆解与路线规划系统”**，负责把模糊目标转化为可执行、可观测、可动态调整的计划。

在 AI Infra 中，Planning 是 Agent 从“单次交互”走向“长程自治”的关键层。它不是让模型直接生成答案，而是让模型先思考“要做什么、按什么顺序做、失败了怎么办”，并把这些思考显式地结构化成计划，再交给下游执行。

## 学习目标

读完本章后，你应能：

1. 解释 Planning 与 prompt engineering、CoT、ReAct 的演进关系。
2. 描述 Planning 的核心循环：分解目标、表示计划、执行步骤、观测结果、动态重规划。
3. 画出 Planning 层的典型架构，并说明 Planner、Plan Store、Executor、Observer、Replan Trigger 等组件的职责边界。
4. 对比 ReAct、Plan-and-Execute、Tree of Thoughts、LLM+P、HuggingGPT、LangGraph planner、OpenAI Agents SDK handoffs、AutoGen planner 等主流方案的设计取舍。
5. 用 `planning_mini` 实现一个最小可用的 Planning Agent，并解释生产落地的关键差异。
6. 识别生产中的典型陷阱：重规划风暴、计划粒度过细/过粗、计划不可验证、与人类协作断层等。

## Planning 与相邻主题的关系

| 主题 | 与 Planning 的关系 | 边界说明 |
|---|---|---|
| [Agent Runtime](/05-agent/agent-runtime/) | Runtime 负责步骤调度、工具调用、生命周期管理；Planning 负责“做什么” | Planning 生成计划，Runtime 执行计划；Runtime 不决定任务拆解策略，只负责把计划项调度到工具/模型/人。 |
| [Memory](/05-agent/memory/) | Memory 提供上下文、历史计划、经验教训；Planning 需要读写 Plan Store 与长期记忆 | Planning 只负责计划本身的语义，Memory 负责存储、检索与向量化。 |
| [Reflection](/05-agent/reflection/) | Reflection 负责从执行结果中提炼失败根因与改进策略，触发重规划 | Planning 响应 Reflection 的输出；Reflection 不直接生成新计划。 |
| [Multi-Agent](/05-agent/multi-agent/) | Multi-Agent 解决“谁来做”，Planning 解决“做什么、按什么顺序做” | 两者常组合：中央 Planner 拆计划，各 Agent 领取子任务执行。 |
| [MCP](/05-agent/mcp/) | MCP 提供标准化的外部能力接入；Planning 通过 Tool/MCP Gateway 使用这些能力 | Planning 不关心 MCP 协议细节，只依赖工具描述与调用结果。 |
| [Tool Use](/05-agent/tool-use/) | Tool Use 负责单次工具调用的语法与结果解析；Planning 决定何时、为何、以什么参数调用 | Planning 把工具调用作为计划中的原子步骤。 |
| [Agent OS](/05-agent/agent-os/) | Agent OS 负责任务/进程的调度、沙箱与资源治理；Planning 生成计划后由 Agent OS 调度执行 | Planning 决定“做什么”，Agent OS 决定“以什么进程/资源做”。 |
| RAG | /06-rag/ | Planning 决定复杂查询的检索顺序与迭代策略。 |

## 本章结构

- [01-background](01-background)：从 prompt engineering 到显式 Planning 的演进。
- [02-core-ideas](02-core-ideas)：任务分解、计划表示、规划循环、静态与动态重规划。
- [03-architecture](03-architecture)：Planning 层的分层架构与各组件职责。
- [04-planning-loop](04-planning-loop)：Plan → Execute → Observe → Replan 的完整循环。
- [05-core-modules](05-core-modules)：核心模块的输入输出与生产注意点。
- [06-source-analysis](06-source-analysis)：主流框架与论文的源码级对比。
- [07-mini-demo](07-mini-demo)：用 `planning_mini` 实现最小 Planning Agent。
- [08-production-practice](08-production-practice)：企业生产落地、集成、SLO 与审计。
- [09-best-practices](09-best-practices)：计划粒度、DAG 优先、触发器设计等清单。
- [10-interview-questions](10-interview-questions)：初/中/高级面试题。
- [11-further-reading](11-further-reading)：论文、文档与延伸阅读。

## 一句话总结

Agent Planning 把“模糊目标”变成“可执行、可观测、可回滚、可重规划”的结构化计划，是 Agent 从“想到哪做到哪”走向“长程自治”的必经之路。

## 本章小结

- Planning 是 Agent 的控制中枢之一，核心职责是目标拆解、计划表示、执行调度与动态调整。
- 它与 Runtime、Memory、Reflection、Multi-Agent、MCP、Tool Use 各司其职，边界清晰才能避免系统耦合。
- 本章将从背景、核心思想、架构、循环、模块、源码、实践到面试题，系统讲解 Planning 的工程落地。

**参考来源**
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [LLM+P: Empowering Large Language Models with Optimal Planning Proficiency](https://arxiv.org/abs/2304.11477)
- [HuggingGPT: Solving AI Tasks with ChatGPT and its Friends in HuggingFace](https://arxiv.org/abs/2303.17580)
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)
