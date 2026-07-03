# 11. 延伸阅读

> 一句话理解：**Multi-Agent 是一个快速发展的交叉领域，官方文档提供 API 细节，论文提供思想脉络，工程文章提供落地经验，相关主题则帮你把 Multi-Agent 放进完整的 AI Infra 版图里理解**。

## 官方文档

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/) — Microsoft 多 Agent 对话编排框架官方文档。
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/) — LangGraph 多 Agent 概念与实现指南。
- [CrewAI Documentation](https://docs.crewai.com/) — 角色驱动的 Multi-Agent 框架文档。
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/) — OpenAI Agents SDK 的 Handoff 机制文档。
- [CAMEL Documentation](https://docs.camel-ai.org/) — 角色扮演与多 Agent 数据合成框架文档。
- [MetaGPT Documentation](https://docs.deepwisdom.ai/main/Main%20Guide/) — 软件公司模拟 Multi-Agent 框架文档。

## 论文

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155) — AutoGen 框架论文，提出 ConversableAgent 与 GroupChat 等抽象。
- [MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) — MetaGPT 论文，用 SOP 模拟软件公司协作。
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — ReAct 范式，是单 Agent 与 Multi-Agent 执行的基础。
- [CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society](https://arxiv.org/abs/2303.17760) — CAMEL 角色扮演与数据合成论文。

## 工程文章

- [Steve Kinney — Multi-Agent Systems](https://stevekinney.com/writing/multi-agent-systems) — Multi-Agent 系统设计思考。
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems) — Agent 记忆系统设计，与 Multi-Agent 共享状态密切相关。
- [LangGraph Blog — Multi-Agent Workflows](https://blog.langchain.dev/langgraph-multi-agent-workflows/) — LangGraph 多 Agent 工作流设计思路。
- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/) — 能力封装演进，对 Agent Skill 设计有参考价值。

## 相关主题

- [Agent Runtime](/05-agent/agent-runtime/) — Multi-Agent 中每个 Agent 的执行容器。
- [Agent Memory](/05-agent/memory/) — Multi-Agent 共享或隔离的长期记忆与 Blackboard 持久化。
- [Agent Reflection](/05-agent/reflection/) — 群体反思与自我纠错是 Multi-Agent 系统的重要能力。
- [MCP](/05-agent/mcp/) — Agent 能力发现与调用协议，Multi-Agent 角色可借此发现彼此能力。
- LLM Gateway（后续主题）— Multi-Agent 调用多模型的统一入口。
- Planning（后续主题）— Coordinator 做任务拆分与重规划的核心能力。
- MCP（后续主题）— Agent 能力发现与调用协议。
- RAG（后续主题）— 多个 Agent 可共享的外部知识检索能力。

## 推荐学习路径

1. **先理解单 Agent**：通读 [Agent Runtime](/05-agent/agent-runtime/) 与 [Agent Memory](/05-agent/memory/)，掌握 ReAct、工具、记忆、状态、可观测。
2. **再理解协作思想**：阅读本主题 [核心思想](02-core-ideas) 与 [协作模式](04-collaboration-patterns)。
3. **动手跑 Mini Demo**：按 [工程实践](07-mini-demo) 运行代码，观察 Registry、Message Bus、Blackboard、Coordinator 如何协作。
4. **对比主流框架**：阅读 [源码分析](06-source-analysis)，理解 AutoGen、LangGraph、CrewAI 等框架的差异。
5. **思考生产问题**：阅读 [企业生产实践](08-production-practice) 与 [最佳实践](09-best-practices)，设计自己的 Multi-Agent 落地路径。

## 本章小结

Multi-Agent 的学习资源涵盖官方文档、论文、工程文章与本手册内的相关主题。建议从单 Agent 基础出发，逐步理解协作思想、动手实验、对比框架、思考生产，形成完整的知识体系。

**参考来源**

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [AutoGen Paper](https://arxiv.org/abs/2308.08155)
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [CAMEL Documentation](https://docs.camel-ai.org/)
- [MetaGPT Documentation](https://docs.deepwisdom.ai/main/Main%20Guide/)
- [MetaGPT Paper](https://arxiv.org/abs/2308.00352)
- [Steve Kinney — Multi-Agent Systems](https://stevekinney.com/writing/multi-agent-systems)
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
