# 1. 背景

## 为什么需要 Agent Runtime？

大模型应用的发展大致经历了三个阶段：

```text
Prompt Engineering → RAG → Agent
```

- **Prompt Engineering**：直接问模型，模型只负责生成文本。
- **RAG**：给模型加上外部知识库，让它能基于检索结果回答。
- **Agent**：让模型能够自主调用工具、分解任务、多轮迭代，最终完成目标。

当进入 Agent 阶段后，简单的 `curl` 调用已经不够用了。一个 Agent 任务通常要：

1. 把用户目标拆成多步计划。
2. 在每一步决定调用哪个工具、传入什么参数。
3. 执行工具并观察结果。
4. 根据结果调整计划，继续循环。
5. 管理会话状态、记忆、权限、超时、失败恢复。
6. 记录完整 trace 供审计与评测。

这些能力如果散落在每个业务应用里，会迅速失控。Agent Runtime 就是要把它们收敛到一个统一的执行层。

## 从“调用模型”到“执行任务”

没有 Runtime 时，一个 Agent 应用通常长这样：

```mermaid
flowchart LR
    A[业务 A] -->|OpenAI SDK + 手写循环| OAI[OpenAI]
    B[业务 B] -->|LangChain + 自定义工具| LLM[LLM]
    C[业务 C] -->|自研 ReAct| LLM2[LLM]
```

每个团队都要重复实现：工具注册、ReAct 循环、状态管理、护栏、trace、错误恢复。

引入 Agent Runtime 后，架构收敛为：

```mermaid
flowchart LR
    A[业务 A] --> RT
    B[业务 B] --> RT
    C[业务 C] --> RT[Agent Runtime]
    RT -->|统一接口| GW[LLM Gateway]
    RT -->|调用| Tool1[数据库]
    RT -->|调用| Tool2[搜索引擎]
    RT -->|调用| Tool3[代码执行]
    GW -->|路由| LLM[vLLM / OpenAI / Triton]
```

Runtime 向上暴露“给定目标，返回结果”的简单接口；向下管理工具调用、LLM 交互、状态与观测。

## Agent Runtime 与相关概念的区别

| 概念 | 核心问题 | 与 Runtime 的关系 |
|---|---|---|
| **Workflow Engine（Airflow/Prefect）** | 按预定义 DAG 执行任务 | Agent Runtime 是动态的、由模型决策的循环，不是固定 DAG |
| **LLM Gateway** | 统一接入多种模型 | Runtime 通过 Gateway 调用模型；Gateway 不管理 Agent 循环 |
| **MCP** | 工具发现与调用协议 | Runtime 可以使用 MCP，也可以直接用 function calling；MCP 不是 Runtime 本身 |
| **Multi-Agent Framework** | 多 Agent 协作 | Runtime 通常管理单个 Agent 的执行；多 Agent 协调在更高层 |
| **Agent OS** | 把 Agent 当作应用管理 | Agent OS 是产品化控制面；Runtime 是其执行底座 |
| **Agent Framework（LangGraph/CrewAI）** | 开发者如何写 Agent 逻辑 | Runtime 是这些框架的运行时支撑，也可独立存在 |

> 一句话：Agent Runtime 是 Agent 的“操作系统内核”，负责调度、隔离、状态、可观测与恢复。

## 为什么现在 Agent Runtime 变得重要？

1. **模型能力变强**：Claude 4.x、GPT-5.x、Gemini 3 等模型已经能在一次调用中完成复杂推理与代码生成，真正稀缺的不再是“聪明的大脑”，而是安全、可控的执行环境（harness）。
2. **任务时长变长**：Agent 从单次秒级调用演进为分钟级、小时级甚至持续运行，需要状态持久化和断点续跑；2025–2026 年 Temporal、Inngest、Restate 等 durable execution 引擎被大规模引入 Agent 场景。
3. **工具越来越多**：企业内 API、数据库、代码执行、浏览器自动化等工具需要统一注册、权限控制与审计；MCP（2026-07-28 规范转向无状态核心）与 A2A v1.0（2026-03 发布）让工具与 Agent 互联开始标准化。
4. **安全要求提高**：Agent 能写代码、调 API、访问数据库，必须隔离、限权、可回滚；E2B、Modal 等基于 Firecracker microVM 的沙箱成为默认选项。
5. **评测要求提高**：Agent 上线前需要任务成功率、轨迹质量、安全合规的系统性评测，倒逼 Runtime 从第一天输出标准化 trace。

## 主流 Agent Runtime / Framework 对比

| 项目 | 定位 | 核心抽象 | 适用场景 |
|---|---|---|---|
| **OpenAI Agents SDK** | OpenAI 生态原生 SDK（基于 Responses API） | Agent + handoffs + guardrails + subagents + 原生沙箱 | 快速落地；2026-04 大版本后支持任意 Chat Completions 兼容模型；2026-09-10 DevDay 起 Codex harness 以 **Agents API**（public beta）形态托管化 |
| **LangGraph** | 生产级状态图编排与 durable execution | StateGraph / checkpoint / edges | 复杂、有状态、需断点续跑的生产工作流 |
| **Google ADK 2.0** | Google 全栈 Agent 开发套件 | Graph workflow + HITL 原语 + skills 生命周期 | Google 生态、多语言（Python/Go/TypeScript） |
| **Claude Agent SDK** | Anthropic 原生 Agent SDK（原 Claude Code SDK） | hooks + subagents + skills | Claude 生态、coding agent、深度 MCP 集成；Claude Code v2.1.x（2026-09/10）把 fork subagents、Agent View、空闲会话压缩做成默认能力 |
| **CrewAI** | 角色化多 Agent 团队 | Role + Task + Crew | 快速原型、角色扮演类任务 |
| **Smolagents** | 轻量级代码优先 Agent | Python code agent | 教学、轻量工具调用 |
| **PydanticAI** | 类型安全 Agent | Typed tools / structured outputs | Python 生态、强类型偏好；可与 Restate 等 durable 引擎组合 |
| **Microsoft Agent Framework** | Azure/企业级 Agent | Actor / message-passing | Azure、企业协作；2026-04 GA 后独立 harness 于 2026-07-22 GA，由 AutoGen 与 Semantic Kernel 合并而来（AutoGen 独立版进入维护模式） |
| **LlamaIndex Workflows** | RAG-first Agent | Indexes + event-driven workflows + AgentWorkflow | 数据密集型、检索质量为核心的任务 |

2025–2026 年的三个行业趋势值得注意：

- **框架收敛**：多 Agent 框架的抽象趋同（graph/actor/事件驱动），MCP 与 A2A 协议成熟后，框架选择从“锁定”变成“可替换组件”。
- **SDK 平台化**：OpenAI Agents SDK（2026-04）与 Google ADK 2.0（2026-05 Python GA）都加入了原生沙箱执行、subagents、skills 生命周期管理，Runtime 能力从“自己拼”走向“开箱即用”。
- **Durable execution 下沉**：LangGraph 自研 checkpointing 之外，Temporal、Inngest、Restate、DBOS 等通用 durable 引擎被用作 Agent 循环的持久化底座。
- **Runtime 托管化（2026 下半年主线）**：头部厂商把自家 harness 变成托管服务——OpenAI **Agents API**（2026-09-10 DevDay public beta，托管 Codex harness：durable sessions、自动上下文压缩、tool search、并行 subagents）、Anthropic **Claude Managed Agents**（2026-04 public beta，按 $0.08/session-hour 计费；2026-10-09 加入 dynamic workflows beta）、AWS **Bedrock AgentCore Managed Harness**（2026-07 GA）。“自建还是购买 Runtime”从架构题变成采购题。

## 本章小结

Agent Runtime 的产生是模型能力进化的必然结果：当模型不仅能生成文本，还能调用工具、执行代码、访问外部系统时，就必须有一个执行层来管理这些行为的边界、状态与可观测性。它既不是 workflow engine，也不是 LLM Gateway，而是介于两者之间、面向 Agent 的动态执行容器。

**参考来源**

- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Google ADK 2.0 Documentation](https://adk.dev/2.0/)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Agent frameworks in 2026: four camps, two protocols and how to choose — genaibrief](https://genaibrief.com/tools/agent-frameworks-survey-2026/)
- [OpenAI Agents API: Do You Still Need to Build an Agent Harness? — ODSC](https://opendatascience.com/openai-agents-api-do-you-still-need-to-build-an-agent-harness/)
- [Claude Managed Agents dynamic workflows (beta), 2026-10-09](https://claude-for.com/guides/claude-managed-agents-dynamic-workflows-2026-10-09)
- [AWS raises AgentCore runtime quotas by up to 5x — InfoWorld](https://www.infoworld.com/article/4192220/aws-raises-agentcore-runtime-quotas-by-up-to-5x-to-help-enterprises-scale-ai-agents.html)
- [Durable AI agents in 2026: long-running workflows with Temporal, Inngest, DBOS, and Restate](https://www.reactify-solutions.com/articles/durable-ai-agents-2026)
- [Agent Runtime 与 Agent OS — Diors.tech](https://www.diors.tech/blog/099-agent-runtime-os)
- [quant67 — Agent 框架工程](https://quant67.com/post/llm-infra/19-agent-framework/19-agent-framework.html)
