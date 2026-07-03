# 延伸阅读

> 一句话理解：**Planning 的理论基础来自经典规划、强化学习与 LLM 推理，工程实现则分布在各大 Agent 框架与工业实践中，推荐阅读顺序是：论文 → 框架文档 → 工程文章 → 源码。**

本章提供论文、框架文档、工程文章与学习路径，帮助读者从理论到实践系统掌握 Planning。

## 论文

### 基础与演进

- [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models](https://arxiv.org/abs/2201.11903)
  - CoT 的开山之作，理解 LLM 逐步推理的基础。

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
  - 推理与行动交错，是 Planning 从隐式到显式的重要过渡。

- [Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models](https://arxiv.org/abs/2305.04091)
  - 先制定计划再求解，是显式 Planning 的重要早期工作。

### 显式 Planning 与搜索

- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
  - 把推理组织成树并搜索，适合需要多路径探索的任务。

- [LLM+P: Empowering Large Language Models with Optimal Planning Proficiency](https://arxiv.org/abs/2304.11477)
  - LLM + 经典规划器（PDDL），适合状态/动作可形式化的问题。

- [HuggingGPT: Solving AI Tasks with ChatGPT and its Friends in HuggingFace](https://arxiv.org/abs/2303.17580)
  - LLM 作为任务规划器，调度多个专家模型。

### Multi-Agent 与协作规划

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)
  - AutoGen 的论文，理解多 Agent 对话式规划。

- [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)
  - 用角色化协作完成复杂软件工程任务，体现分层 Planning。

### 反思与自我改进

- [Reflexion: Self-Reflective Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
  - 理解 Reflection 如何与 Planning 配合。

- [Self-Refine: Iterative Self-Refinement with Feedback-LLMs](https://arxiv.org/abs/2303.17651)
  - 自我迭代的生成-反馈-改进循环。

## 框架文档

- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
  - LangGraph 的计划概念与图结构执行。

- [LangChain Planning for Agents](https://blog.langchain.dev/planning-for-agents/)
  - LangChain 对 Planning 的工程设计思考。

- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
  - OpenAI Agents SDK 中的 Agent 转交机制。

- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)
  - AutoGen 的 Planning 教程与多 Agent 协作示例。

- [Semantic Kernel Planners](https://learn.microsoft.com/en-us/semantic-kernel/concepts/planning)
  - 微软 Semantic Kernel 的 Planner 能力介绍。

## 工程文章

- [Building LLM Agents: A Practical Guide](https://www.philschmid.de/llm-agent)
  - 关于 LLM Agent 构建的实用指南，涵盖 Planning。

- [The Rise and Potential of Large Language Model Based Agents: A Survey](https://arxiv.org/abs/2309.07864)
  - LLM Agent 综述，Planning 是其中重要章节。

- [A Survey on Large Language Model based Autonomous Agents](https://arxiv.org/abs/2308.11432)
  - 另一篇高质量综述，系统梳理 Agent 架构。

## 相关主题链接

本章所在 AI Infra Handbook 的相关主题：

- [Agent Runtime](/05-agent/agent-runtime/)：Planning 层的执行伙伴，负责任务调度与生命周期。
- [Memory](/05-agent/memory/)：为 Planning 提供上下文、历史计划与经验教训。
- [Reflection](/05-agent/reflection/)：从失败中总结，驱动 Planning 重规划。
- [Multi-Agent](/05-agent/multi-agent/)：与 Planning 协作，解决“谁来做”。
- [MCP](/05-agent/mcp/)：为 Planning 提供标准化的外部能力接入。
- [Tool Use](/05-agent/tool-use/)：Planning 把工具调用作为计划中的原子步骤。

## 推荐学习路径

### 路径一：快速上手（1-2 周）

1. 阅读 [ReAct 论文](https://arxiv.org/abs/2210.03629) 与 [LangChain Planning 博客](https://blog.langchain.dev/planning-for-agents/)。
2. 用 LangGraph 或 OpenAI Agents SDK 实现一个 Plan-and-Execute 原型。
3. 阅读本章的 [02-core-ideas](02-core-ideas) 与 [07-mini-demo](07-mini-demo)。

### 路径二：系统深入（1-2 月）

1. 精读 ToT、LLM+P、HuggingGPT 三篇论文。
2. 对比 ReAct、Plan-and-Execute、LangGraph、AutoGen 的源码实现。
3. 阅读本章的 [03-architecture](03-architecture)、[04-planning-loop](04-planning-loop)、[05-core-modules](05-core-modules)。
4. 设计并实现一个带 DAG 执行、Observer、Replan Trigger 的 Planning 层。

### 路径三：生产落地（持续）

1. 阅读 [08-production-practice](08-production-practice) 与 [09-best-practices](09-best-practices)。
2. 在真实业务中接入 Planning 层，重点验证计划验证、重规划风暴防护、HITL、审计。
3. 建立 SLO 监控体系，持续优化分解模板与模型策略。
4. 定期复盘失败案例，沉淀到 Plan Memory。

## 本章小结

- Planning 的理论基础包括 CoT、ReAct、显式规划、树搜索、经典规划、多 Agent 协作与 Reflection。
- 工程实现可重点参考 LangGraph、OpenAI Agents SDK、AutoGen、Semantic Kernel。
- 推荐按“快速上手 → 系统深入 → 生产落地”的路径学习，并结合本主题其他章节建立完整知识网络。

**参考来源**
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Planning for Agents - LangChain Blog](https://blog.langchain.dev/planning-for-agents/)
- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [LLM+P: Empowering Large Language Models with Optimal Planning Proficiency](https://arxiv.org/abs/2304.11477)
- [HuggingGPT: Solving AI Tasks with ChatGPT and its Friends in HuggingFace](https://arxiv.org/abs/2303.17580)
- [LangGraph Plans](https://langchain-ai.github.io/langgraph/concepts/plans/)
- [OpenAI Agents SDK Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [AutoGen Planning Tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/planning.html)
