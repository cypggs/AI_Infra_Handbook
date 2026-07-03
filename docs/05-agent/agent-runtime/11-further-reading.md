# 11. 延伸阅读

## 官方文档（必读）

- [OpenAI Agents SDK](https://platform.openai.com/docs/guides/agents)
  - 厂商原生 Agent SDK，学习 Agent、Tool、Handoffs、Guardrails、Tracing 设计。
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
  - 生产级状态图编排，重点看 StateGraph、Persistence、Human-in-the-loop。
- [LangChain Function Calling](https://python.langchain.com/docs/concepts/tool_calling/)
  - 工具调用与 JSON Schema 生成机制。
- [Smolagents Documentation](https://huggingface.co/docs/smolagents/index)
  - 轻量级代码优先 Agent 框架。
- [PydanticAI Documentation](https://ai.pydantic.dev/)
  - 类型安全 Agent 框架。
- [CrewAI Documentation](https://docs.crewai.com/)
  - 角色化多 Agent 团队框架。

## 论文

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
  - ReAct 范式的原始论文。
- [Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761)
  - 模型使用工具的早期工作。

## 工程文章

- [Agent Runtime 与 Agent OS：2026 年 AI 产品的工程底座 — Diors.tech](https://www.diors.tech/blog/099-agent-runtime-os)
  - 中文视角下的 Runtime 与 Agent OS 边界。
- [quant67 — Agent 框架工程](https://quant67.com/post/llm-infra/19-agent-framework/19-agent-framework.html)
  - 大模型基础设施工程系列中的 Agent 框架篇。
- [从 Function Call 到 MCP → SKILLS](https://crossoverjie.top/2026/02/03/AI/MCP-Skills-intro/)
  - 工具能力封装从 function call 到 skills 的演进。
- [Agent Memory Systems — Steve Kinney](https://stevekinney.com/writing/agent-memory-systems)
  - Agent 记忆系统设计。

## 云厂商 Runtime

- [AWS Bedrock Agents / AgentCore](https://docs.aws.amazon.com/bedrock/)
- [Azure AI Agent Service](https://learn.microsoft.com/en-us/azure/ai-services/agents/)
- [Google Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)

## 相关主题

- [Agent Runtime 详解](/05-agent/agent-runtime/) — 本主题。
- [Memory 详解](/05-agent/memory/) — Agent 的记忆系统：工作记忆、长期记忆、向量检索与持久化。
- [Multi-Agent 详解](/05-agent/multi-agent/) — 多 Agent 协作、角色定义、协调调度与共享黑板。
- [Reflection 详解](/05-agent/reflection/) — Agent 自我反思与纠错：生成、批判、评估、修订闭环。
- [MCP 详解](/05-agent/mcp/) — Agent 能力发现与调用协议，Runtime 的重要搭档。
- [Planning 详解](/05-agent/planning/) — 复杂任务分解、计划表示与动态重规划，与 Runtime 内嵌 Planner 形成分层。
- [Tool Use 详解](/05-agent/tool-use/) — Agent 工具调用层：Schema、解析、校验、执行与结果格式化，Runtime 的直接依赖。
- [Agent OS 详解](/05-agent/agent-os/) — Agent 运行时操作系统：进程、调度、沙箱、Workspace 与资源治理，Runtime 的上层治理者。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — Agent Runtime 通常通过 Gateway 调用模型。
- [vLLM 详解](/04-llmops/vllm/) — 可作为 Agent Runtime 的上游推理引擎。
- [SGLang 详解](/04-llmops/sglang/) — 结构化生成与 LLM Program 执行引擎。
- [Triton Inference Server 详解](/04-llmops/triton/) — 多框架推理服务入口。
- [Ray 详解](/03-ai-platform/ray/) — 分布式 Python 计算框架，可作为大规模 Agent 部署的执行底座（actor 池、Serve、Data）。

## 推荐学习路径

1. 先读 ReAct 论文，理解 reasoning + acting 的基础。
2. 用 OpenAI Agents SDK 跑通一个带工具调用的简单 Agent。
3. 用 LangGraph 实现一个带 checkpoint 的多步 Agent。
4. 阅读本主题的 [Mini Demo](./07-mini-demo)，手写一个最小 ReAct Runtime。
5. 结合 [生产实践](./08-production-practice) 思考沙箱、护栏、可观测与评测落地。

## 本章小结

Agent Runtime 的生态系统正在快速分化：OpenAI Agents SDK 适合快速落地，LangGraph 适合复杂生产工作流，Smolagents 适合教学，PydanticAI 适合强类型应用。结合本主题的 [Mini Demo](./07-mini-demo)、[生产实践](./08-production-practice) 与 [最佳实践](./09-best-practices)，可以从理论到工程全面掌握 Agent Runtime。

**参考来源**

- [OpenAI Agents SDK Docs](https://platform.openai.com/docs/guides/agents)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Smolagents Docs](https://huggingface.co/docs/smolagents/index)
- [PydanticAI Docs](https://ai.pydantic.dev/)
- [Diors.tech — Agent Runtime 与 Agent OS](https://www.diors.tech/blog/099-agent-runtime-os)
- [quant67 — Agent 框架工程](https://quant67.com/post/llm-infra/19-agent-framework/19-agent-framework.html)
