# 6. 源码分析

> 一句话理解：现代 Agent Runtime 的源码核心可以概括为“**一个状态机 + 一套插件契约 + 统一的工具/观测接口**”；本节以 OpenAI Agents SDK 和 LangGraph 为主，结合 Smolagents 与 PydanticAI，说明关键代码组织与扩展点。

## 分析对象选择

| 项目 | 仓库/文档 | 定位 | 分析重点 |
|---|---|---|---|
| **OpenAI Agents SDK** | [openai.github.io/openai-agents-python](https://openai.github.io/openai-agents-python/) | 厂商原生、快速落地 | Agent loop、handoffs、guardrails、tracing、subagents、沙箱 |
| **LangGraph** | [github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 生产级状态图编排 | StateGraph、checkpoint、durable execution、HITL |
| **Smolagents** | [github.com/huggingface/smolagents](https://github.com/huggingface/smolagents) | 轻量代码优先 | Minimal loop、code agent、tool execution |
| **PydanticAI** | [github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | 类型安全 Agent | Typed tools、result validation、model-agnostic |

> 注：开源项目迭代较快，本节基于 2026 年 10 月主流版本分析（LangGraph 1.2.x、smolagents 1.26、PydanticAI 2.5x），具体文件名可能随版本微调。

## OpenAI Agents SDK

OpenAI Agents SDK 是“SDK 式”Runtime 的代表，核心设计目标是最小化样板代码。它构建在 **Responses API** 之上——模型推理与内置工具（web search、file search、code interpreter、computer use、远程 MCP 工具）在一次服务端调用中完成，Assistants API 已于 2026 年中正式废弃。

### 核心抽象

```python
from agents import Agent, Runner

agent = Agent(
    name="MathAssistant",
    instructions="你是一个数学助手。",
    tools=[calculator],
)

result = await Runner.run(agent, "计算 25 * 4 + 10")
```

三个核心原语：

- **Agent**：包含 name、instructions、tools、handoffs、guardrails。
- **Runner**：执行 Agent loop，管理状态与 trace。
- **Tool**：普通 Python 函数，通过 `@function_tool` 装饰器注册。

### Agent Loop

Runner 内部实现了一个标准的 ReAct 循环：

1. 把 `instructions + user input + tool schemas` 发给模型。
2. 模型返回 content 或 `tool_calls`。
3. 如果是 tool_calls，Runner 并行执行工具，把结果追加到 messages。
4. 循环直到模型输出最终答案或达到最大步数。

### 2026-04 大版本：从“OpenAI 专用”到“通用 harness”

2026 年 4 月的版本（v0.14–0.15）是该 SDK 自实验性 Swarm 项目以来最大的改版，要点：

- **原生沙箱执行**：Agent 可以在受控沙箱里检查文件、运行命令、改代码；首发集成 Blaxel、Cloudflare、Daytona、E2B、Modal、Runloop、Vercel 等沙箱供应商。
- **Harness 架构**：把控制面（凭证、编排）与计算面（沙箱执行）分离，降低凭证泄露风险。
- **Subagents**：父 Agent 派生并行子 Agent，子 Agent 上下文隔离。
- **Code Mode**：面向代码生成/编辑场景的优化模式。
- **模型解绑**：通过 Chat Completions 兼容端点支持 100+ 模型（Claude、Gemini、Llama、DeepSeek 等）。
- **三层护栏**：input / output / tool 三层并行执行；2026-06 增加防提示注入的 Lockdown Mode。

### 2026-07→10 增量：工具编排、会话与测试

| 版本 | 日期 | 关键变化 |
|---|---|---|
| v0.19.0 | 2026-07-27 | **Programmatic Tool Calling**：模型生成 JavaScript 编排合格工具（per-tool `allowed_callers`），与 streaming/guardrails/approvals/sessions/RunState 全链路集成；新增 `agents.decorators` 与 `@tool` 别名 |
| v0.20.0 | 2026-08-11 | 默认模型切换为 `gpt-5.6-luna`；`RunState.add_input()` 暂存 durable 用户输入；同时支持 MCP Python SDK v1 与 v2（stdio / SSE / Streamable HTTP） |
| v0.21.0 | 2026-08-15 | `agents.testing` provider 无关测试 API（无需真实 provider 的确定性测试）；RunState 中断快照加固、递归 agent-tool 审批 |
| v0.22.x | 2026-09 | session compaction（含压缩期间并发写安全）；MCP server 级 guardrails；Unix-local 沙箱环境隔离可配置 |
| v0.23.0 | 2026-10-02 | 沙箱 Docker removal 保护、可配置的 memory consolidation 轮数；会话历史加密扫描预算 |
| v0.24.0 | 2026-10-15 | MCP annotations 透传到转换后的工具；**有待审批请求时推迟 compaction** |

这一阶段的演进主题：**工具从“schema 列表”走向“可编排程序”，会话从“内存对象”走向“可恢复 durable 状态”，测试从“打 provider”走向“provider 无关”**。

### OpenAI Agents API：harness 的托管化（2026-09-10 public beta）

DevDay 2026 上 OpenAI 把内部 Codex harness 以 **Agents API** 形态开放（public beta）：durable sessions、自动上下文压缩、tool search（按需检索工具定义而非全量注入）、并行 subagents，沙箱可选 OpenAI 托管 / 自托管 / 第三方。官方口径把 Agents API 与 Agents SDK 明确分层：**API 托管更多 harness 职责（会话、压缩、工具检索），SDK 把编排控制权留给应用**。这是 2026 年“Runtime 作为产品品类”成立的标志性事件——自建 Runtime 的必要性要从“能力缺失”重新论证为“控制与定制需求”。

### Handoffs

Handoffs 让 Agent 可以把任务交给另一个 Agent：

```python
triage_agent = Agent(
    name="Triage",
    handoffs=[sales_agent, support_agent],
)
```

Runtime 会把 `handoff` 当作一种特殊 tool call 处理，切换当前 Agent 的 instructions 和 tools。

### Guardrails 与 Tracing

- Guardrails 可以在输入/输出/工具三层配置校验函数，并行执行。
- Tracing 默认集成 OpenAI 平台的 trace UI，记录每轮调用、工具执行、token 消耗。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 极简 API，快速原型 | 最强能力（内置工具、Computer Use）仍绑定 OpenAI 模型 |
| 原生 handoffs、subagents、guardrails、tracing、沙箱 | 复杂状态机支持不如 LangGraph |
| 2026 起支持任意 Chat Completions 兼容模型 | Python 优先，TypeScript 支持滞后 |
| 内置 MCP 支持 | 多 Agent 协作能力不如 LangGraph |

## LangGraph

LangGraph 是“图编排式”Runtime 的代表，核心抽象是 `StateGraph`。LangChain 与 LangGraph 于 2025-10-22 同时发布 1.0 GA；2026 年的分工是：**LangChain 提供高层 Agent API（create_agent、middleware），LangGraph 是底下的编排/运行时引擎**，1.2.x 版本主要在打磨 durable execution 的正确性（resume 语义、子图恢复、checkpoint 清理）——例如 1.2.16（2026-10-16）集中修复 resume/interrupt 与 checkpoint 写入边界，`langgraph-checkpoint-postgres` 3.2.0（2026-10-14）为 PostgresSaver 增加 prune（checkpoint 清理）。

### 核心抽象

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(State)
graph.add_node("planner", planner_node)
graph.add_node("executor", executor_node)
graph.add_edge("planner", "executor")
graph.add_conditional_edges("executor", should_continue, {"continue": "planner", "end": END})

app = graph.compile()
result = app.invoke({"task": "..."})
```

关键设计：

- **State**：一个 TypedDict / Pydantic model，所有节点共享。
- **Node**：处理 State 的函数。
- **Edge**：控制流转条件。
- **Checkpoint**：把 State 持久化，支持中断/恢复/time-travel。

### 为什么 LangGraph 适合生产

1. **显式状态管理**：所有中间结果都在 State 里，可审计、可调试。
2. **持久化**：内置 Postgres/Redis/SQLite checkpointer；2026 年新增 checkpoint 清理（prune）能力。
3. **Human-in-the-loop**：通过 `interrupt` 节点实现人工确认。
4. **可观测**：与 LangSmith 深度集成，支持逐节点 state 检查与 trace 回放。
5. **平台化**：LangGraph Platform / Server 提供托管的运行时与部署（langgraph-sdk、langgraph-prebuilt 持续迭代）。

### Agent Loop 在 LangGraph 中的表达

一个典型的 ReAct Agent 在 LangGraph 中表达为：

```text
start → agent_node → tools_node → agent_node → ... → end
```

`agent_node` 调用 LLM，`tools_node` 执行工具，条件边决定继续还是结束。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 状态显式、可持久化 | 学习曲线较陡 |
| durable execution 语义完善（恢复/重放/time-travel） | 简单任务样板代码多 |
| 生产可观测性强 | 依赖 LangChain 生态 |

## Smolagents

Smolagents 是 Hugging Face 推出的轻量 Agent 框架，核心特色是“代码优先”。

### 核心设计

- Agent 直接生成 Python 代码来调用工具，而不是生成 JSON tool call。
- 代码在一个受限的 Python 解释器中执行。
- 适合教学和小型任务。

```python
from smolagents import CodeAgent, HfApiModel

agent = CodeAgent(tools=[calculator], model=HfApiModel())
agent.run("计算 25 * 4 + 10")
```

2026 年的定位是“小而稳的库”：v1.26（2026-05）之后进入低频发版节奏；该版本移除了远程 WasmExecutor（安全面收敛），新增 Exa 作为 WebSearch 选项。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 极简，几乎没有抽象 | 不适合复杂多步任务 |
| 代码生成能力强 | 安全风险需要严格控制 |
| 易于理解 Agent 循环 | 生态与可观测性较弱 |

## PydanticAI

PydanticAI 由 Pydantic 团队推出，核心特色是类型安全。2026 年主版本已到 2.5x（MIT 协议），保持每周发版节奏。

### 核心设计

- 工具输入/输出、模型输出都通过 Pydantic model 校验。
- 与 FastAPI 风格类似，对 Python 开发者友好。
- 模型无关，可切换 OpenAI、Anthropic、Gemini 等。
- 与 Restate 等 durable execution 引擎有一等集成（2025-11），可把 Agent 调用变成 durable 函数。

```python
from pydantic_ai import Agent

agent = Agent(model="openai:gpt-5", result_type=Answer)

@agent.tool
def calculator(ctx, expr: str) -> str:
    ...
```

### 优点与局限

| 优点 | 局限 |
|---|---|
| 强类型、易维护 | 复杂工作流编排能力一般 |
| 模型无关 | 生态较新 |
| 结构化输出校验 | 多 Agent 协作支持有限 |

## 其他框架 2026 速览

| 项目 | 2026 年状态 | 一句话点评 |
|---|---|---|
| **Google ADK 2.0** | Python GA（2026-05）、Go（06）、TypeScript（08）；graph workflow、HITL 原语、skills 生命周期管理；Apache 2.0 | Google 生态的首选，多语言覆盖最全 |
| **Claude Agent SDK**（原 Claude Code SDK） | Claude Code v2.1.x（2026-09/10）：subagent 结果以带标记 header 回注防注入（v2.1.278）、fork subagents 默认开启、`autoCompactWindow`、Agent View（`claude agents`）；核心仍是 hooks + subagents + skills | coding agent 场景的强候选；生产使用需注意权限默认拒绝 |
| **xAI Grok Build** | 2026-07 开源（约 132 万行 Rust，ACP 协议）：leader-follower subagents、自动上下文压缩 | 自研 Runtime 的完整开源参照，适合研究 harness 工程 |
| **Microsoft Agent Framework** | AutoGen 与 Semantic Kernel 合并，1.0 GA（2026-04）；独立 harness 于 2026-07-22 GA；AutoGen 独立版进入维护模式 | 企业/Azure 场景；actor + 消息传递模型 |
| **CrewAI** | 持续活跃，角色化 crew + 企业版 | 快速原型与角色扮演类任务 |
| **LlamaIndex Workflows** | 1.0 线成熟，AgentWorkflow + 事件驱动 | 检索/RAG 为核心的数据密集型任务 |

框架选择的 2026 共识：MCP / A2A 协议成熟后，框架不再构成锁定——**选型看的是状态管理、持久化、可观测与团队熟悉度，而不是“哪家协议支持多”**。

## 共同模式总结

| 能力 | OpenAI SDK | LangGraph | Smolagents | PydanticAI |
|---|---|---|---|---|
| 核心抽象 | Agent / Runner | StateGraph | CodeAgent | Agent |
| 状态管理 | 隐式 | 显式 State + durable execution | 隐式 | 隐式 |
| 工具注册 | 装饰器 | 函数/工具节点 | 列表 | 装饰器 |
| 持久化 | 弱（依赖外部 harness） | 强（checkpoint/journal） | 无 | 弱（可接 Restate） |
| 可观测 | 内置 trace（OTel 可导出） | LangSmith / OTel | 弱 | OTel / Langfuse 等 |
| 沙箱 | 原生（2026-04 起） | 需自行集成 | 解释器内受限执行 | 需自行集成 |
| 最佳场景 | 快速落地、SDK 平台化 | 复杂生产工作流 | 教学/轻量 | 强类型应用 |

## 本章小结

OpenAI Agents SDK、LangGraph、Smolagents、PydanticAI 代表了 Agent Runtime 的四种设计取向：SDK 快速落地、图编排生产级、代码生成极简、类型安全可维护。2025–2026 年的共同演进方向是：原生沙箱执行、subagents、skills 化工具管理、durable execution、OpenTelemetry 可观测——理解这些抽象的差异与收敛趋势，有助于在自己的场景中做出合理选型。

**参考来源**

- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK Changelog（v0.19–v0.24，2026-07→10）](https://www.gradually.ai/en/changelogs/openai-agents-sdk/)
- [OpenAI Agents API: Do You Still Need to Build an Agent Harness? — ODSC](https://opendatascience.com/openai-agents-api-do-you-still-need-to-build-an-agent-harness/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph Releases (GitHub)](https://github.com/langchain-ai/langgraph/releases)
- [Smolagents GitHub](https://github.com/huggingface/smolagents)
- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [Google ADK 2.0](https://adk.dev/2.0/)
- [Claude Code Releases（GitHub）](https://github.com/anthropics/claude-code/releases)
- [Grok Build Open Source: xAI Agent Harness Architecture](https://dailyaiworld.com/workflow/grok-build-open-source-harness-workflow-2026)
- [Claude Agent SDK vs OpenAI Agents SDK vs Google ADK: The 2026 Vendor SDK Showdown](https://niteagent.com/blog/vendor-agent-sdk-comparison-2026/)
- [AI Agent Frameworks Compared 2026](https://agentmelt.com/blog/ai-agent-frameworks-compared-2026/)
