# 11. 延伸阅读

## 官方文档（必读）

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
  - 厂商原生 Agent SDK，学习 Agent、Tool、Handoffs、Guardrails、Tracing；2026-04 版重点看 subagents 与原生沙箱，2026-07→10 增量看 Programmatic Tool Calling（v0.19）、`agents.testing`（v0.21）与 session compaction（v0.22+）。
- [OpenAI Agents SDK Changelog](https://www.gradually.ai/en/changelogs/openai-agents-sdk/)
  - v0.19.0（2026-07-27）→ v0.24.0（2026-10-15）逐版本演进记录。
- [OpenAI Agents API（DevDay 2026）](https://opendatascience.com/openai-agents-api-do-you-still-need-to-build-an-agent-harness/)
  - 托管版 Codex harness：durable sessions、自动压缩、tool search、并行 subagents；与 Agents SDK 的分层口径。
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
  - 生产级状态图编排，重点看 StateGraph、Persistence、Human-in-the-loop。
- [LangChain Function Calling](https://python.langchain.com/docs/concepts/tool_calling/)
  - 工具调用与 JSON Schema 生成机制。
- [Google ADK 2.0](https://adk.dev/2.0/)
  - Google 全栈 Agent 开发套件：graph workflow、HITL、skills 生命周期，Python/Go/TypeScript 三语言。
- [Smolagents Documentation](https://huggingface.co/docs/smolagents/index)
  - 轻量级代码优先 Agent 框架。
- [PydanticAI Documentation](https://ai.pydantic.dev/)
  - 类型安全 Agent 框架。
- [Claude Code Releases（GitHub）](https://github.com/anthropics/claude-code/releases)
  - Claude Agent SDK 的宿主：v2.1.x（2026-09/10）重点看 subagent 回注注入防御、fork subagents、`autoCompactWindow` 与 Agent View。
- [Claude Managed Agents dynamic workflows (beta), 2026-10-09](https://claude-for.com/guides/claude-managed-agents-dynamic-workflows-2026-10-09)
  - 托管 Runtime 的多阶段 workflow run 与事件流。
- [CrewAI Documentation](https://docs.crewai.com/)
  - 角色化多 Agent 团队框架。

## 协议与标准

- [MCP 2026-07-28 Specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
  - MCP 迄今最大改版：无状态核心、MRTR、OAuth 加固；由 Linux Foundation Agentic AI Foundation 治理。
- [A2A Protocol](https://a2a-protocol.org)
  - Agent-to-Agent 协作协议，v1.0（2026-03）起进入生产可用；与 MCP 互补。
- [OpenTelemetry Semantic Conventions — GenAI](https://github.com/open-telemetry/semantic-conventions-genai)
  - Agent 可观测的移植性标准：span 树 `invoke_agent` → `chat` → `execute_tool`（注意仍为 Development 状态）。

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
- [Best AI agent frameworks (2026) — Braintrust](https://www.braintrust.dev/articles/best-ai-agent-frameworks-2026)
  - 框架选型与 eval 落地的一线经验。
- [AI Agent Evaluation (2026) — Morph](https://www.morphllm.com/ai-agent-evaluation)
  - 生产环境 Agent 评测的指标、框架与常见失败模式。
- [Durable AI agents in 2026 — Reactify](https://www.reactify-solutions.com/articles/durable-ai-agents-2026)
  - Temporal / Inngest / DBOS / Restate 在 Agent 场景的组合用法。

## 云厂商 Runtime

- [AWS Bedrock Agents / AgentCore](https://docs.aws.amazon.com/bedrock/)
- [Azure AI Agent Service](https://learn.microsoft.com/en-us/azure/ai-services/agents/)
- [Google Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)

## 沙箱与代码执行

- [E2B Documentation](https://docs.e2b.dev/)
  - Firecracker microVM 沙箱的事实标准，跑不可信 LLM 生成代码。
- [E2B Product Updates](https://e2b.dev/product-updates)
  - 2026-09/10 重点：v2 sandbox endpoints 与 CLI fork（09-21）、E2B Embed 自托管（09-14）、仅文件系统快照与暂停模式（10-12）。
- [Modal Sandboxes](https://modal.com/docs)
  - gVisor 隔离 + GPU，VM Sandboxes 于 2026-10-01 GA。
- [Grok Build Open Source: xAI Agent Harness Architecture](https://dailyaiworld.com/workflow/grok-build-open-source-harness-workflow-2026)
  - 2026-07 开源的完整 harness 实现（Rust/ACP），leader-follower subagents 与自动压缩的工程参照。
- [Temporal Durable AI Agents](https://docs.temporal.io/ai)
  - Durable execution 在 Agent 场景的模式与 cookbook。

## 相关主题

- [Agent Runtime 详解](/05-agent/agent-runtime/) — 本主题。
- [Memory 详解](/05-agent/memory/) — Agent 的记忆系统：工作记忆、长期记忆、向量检索与持久化。
- [Multi-Agent 详解](/05-agent/multi-agent/) — 多 Agent 协作、角色定义、协调调度与共享黑板。
- [Reflection 详解](/05-agent/reflection/) — Agent 自我反思与纠错：生成、批判、评估、修订闭环。
- [MCP 详解](/05-agent/mcp/) — Agent 能力发现与调用协议，Runtime 的重要搭档。
- [Planning 详解](/05-agent/planning/) — 复杂任务分解、计划表示与动态重规划，与 Runtime 内嵌 Planner 形成分层。
- [Personal AI Agent 详解](/05-agent/personal-agent/) — 常驻个人 Agent 的运行时形态：每用户沙箱、主动循环与权限门。
- [Tool Use 详解](/05-agent/tool-use/) — Agent 工具调用层：Schema、解析、校验、执行与结果格式化，Runtime 的直接依赖。
- [Agent OS 详解](/05-agent/agent-os/) — Agent 运行时操作系统：进程、调度、沙箱、Workspace 与资源治理，Runtime 的上层治理者。
- [Benchmark + Evaluation 详解](/07-ai-sre/benchmark-evaluation/) — Agent 可评估性：trace-based eval、工具调用正确性、延迟/成本/鲁棒性评测。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — Agent Runtime 通常通过 Gateway 调用模型。
- [vLLM 详解](/04-llmops/vllm/) — 可作为 Agent Runtime 的上游推理引擎。
- [SGLang 详解](/04-llmops/sglang/) — 结构化生成与 LLM Program 执行引擎。
- [Triton Inference Server 详解](/04-llmops/triton/) — 多框架推理服务入口。
- [Ray 详解](/03-ai-platform/ray/) — 分布式 Python 计算框架，可作为大规模 Agent 部署的执行底座（actor 池、Serve、Data）。

## 推荐学习路径

1. 先读 ReAct 论文，理解 reasoning + acting 的基础。
2. 用 OpenAI Agents SDK 跑通一个带工具调用的简单 Agent；再试 Google ADK 2.0 的 graph workflow。
3. 用 LangGraph 实现一个带 checkpoint 的多步 Agent。
4. 阅读本主题的 [Mini Demo](./07-mini-demo)，手写一个最小 ReAct Runtime。
5. 结合 [生产实践](./08-production-practice) 思考沙箱（E2B/Modal）、durable execution（Temporal/Inngest）、可观测（OTel GenAI）与评测落地。

## 本章小结

Agent Runtime 的生态系统正在快速分化又快速收敛：OpenAI Agents SDK（2026-04 平台化，07→10 迭代 v0.19–v0.24：Programmatic Tool Calling、session compaction、`agents.testing`）、Google ADK 2.0、Claude Agent SDK（v2.1.x 并行化与压缩默认化）在 SDK 层补齐沙箱/subagents/skills；OpenAI Agents API（2026-09-10）、Claude Managed Agents（dynamic workflows beta，2026-10-09）、Bedrock AgentCore Managed Harness（2026-07 GA）把 Runtime 变成可采购的托管品类；LangGraph 守住生产级状态编排与 durable execution；MCP（2026-07-28 无状态核心）与 A2A（v1.0）把互操作层标准化。结合本主题的 [Mini Demo](./07-mini-demo)、[生产实践](./08-production-practice) 与 [最佳实践](./09-best-practices)，可以从理论到工程全面掌握 Agent Runtime。

**参考来源**

- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Google ADK 2.0](https://adk.dev/2.0/)
- [Smolagents Docs](https://huggingface.co/docs/smolagents/index)
- [PydanticAI Docs](https://ai.pydantic.dev/)
- [The Agent Protocol Stack in 2026](https://www.agenticfabriq.com/blog/agent-protocol-stack-2026)
- [Diors.tech — Agent Runtime 与 Agent OS](https://www.diors.tech/blog/099-agent-runtime-os)
- [quant67 — Agent 框架工程](https://quant67.com/post/llm-infra/19-agent-framework/19-agent-framework.html)
