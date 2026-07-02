# 6. 源码分析

> 一句话理解：现代 Agent Runtime 的源码核心可以概括为“**一个状态机 + 一套插件契约 + 统一的工具/观测接口**”；本节以 OpenAI Agents SDK 和 LangGraph 为主，结合 Smolagents 与 PydanticAI，说明关键代码组织与扩展点。

## 分析对象选择

| 项目 | 仓库/文档 | 定位 | 分析重点 |
|---|---|---|---|
| **OpenAI Agents SDK** | [platform.openai.com/docs/guides/agents](https://platform.openai.com/docs/guides/agents) | 厂商原生、快速落地 | Agent loop、handoffs、guardrails、tracing |
| **LangGraph** | [github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 生产级状态图编排 | StateGraph、checkpoint、edges、HITL |
| **Smolagents** | [github.com/huggingface/smolagents](https://github.com/huggingface/smolagents) | 轻量代码优先 | Minimal loop、code agent、tool execution |
| **PydanticAI** | [github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | 类型安全 Agent | Typed tools、result validation、model-agnostic |

> 注：开源项目迭代较快，本节基于 2026 年中主流分支结构进行分析，具体文件名可能随版本微调。

## OpenAI Agents SDK

OpenAI Agents SDK 是“SDK 式”Runtime 的代表，核心设计目标是最小化样板代码。

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

- Guardrails 可以在输入/输出层配置校验函数。
- Tracing 默认集成 OpenAI 平台的 trace UI，记录每轮调用、工具执行、token 消耗。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 极简 API，快速原型 | 深度绑定 OpenAI 模型 |
| 原生 handoffs、guardrails、tracing | 复杂状态机支持较弱 |
| 内置 MCP 支持 | 多 Agent 协作能力不如 LangGraph |

## LangGraph

LangGraph 是“图编排式”Runtime 的代表，核心抽象是 `StateGraph`。

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
2. **持久化**：内置 Postgres/Redis/MemorySaver checkpointer。
3. **Human-in-the-loop**：通过 `interrupt` 节点实现人工确认。
4. **可观测**：与 LangSmith 深度集成。

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
| 复杂工作流表达力强 | 简单任务样板代码多 |
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

### 优点与局限

| 优点 | 局限 |
|---|---|
| 极简，几乎没有抽象 | 不适合复杂多步任务 |
| 代码生成能力强 | 安全风险需要严格控制 |
| 易于理解 Agent 循环 | 生态与可观测性较弱 |

## PydanticAI

PydanticAI 由 Pydantic 团队推出，核心特色是类型安全。

### 核心设计

- 工具输入/输出、模型输出都通过 Pydantic model 校验。
- 与 FastAPI 风格类似，对 Python 开发者友好。
- 模型无关，可切换 OpenAI、Anthropic、Gemini 等。

```python
from pydantic_ai import Agent

agent = Agent(model="openai:gpt-4o", result_type=Answer)

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

## 共同模式总结

| 能力 | OpenAI SDK | LangGraph | Smolagents | PydanticAI |
|---|---|---|---|---|
| 核心抽象 | Agent / Runner | StateGraph | CodeAgent | Agent |
| 状态管理 | 隐式 | 显式 State | 隐式 | 隐式 |
| 工具注册 | 装饰器 | 函数/工具节点 | 列表 | 装饰器 |
| 持久化 | 弱 | 强 | 无 | 弱 |
| 可观测 | 内置 trace | LangSmith | 弱 | 弱 |
| 最佳场景 | OpenAI 快速落地 | 复杂生产工作流 | 教学/轻量 | 强类型应用 |

## 本章小结

OpenAI Agents SDK、LangGraph、Smolagents、PydanticAI 代表了 Agent Runtime 的四种设计取向：SDK 快速落地、图编排生产级、代码生成极简、类型安全可维护。理解它们的抽象差异，有助于在自己的场景中做出合理选型。

**参考来源**

- [OpenAI Agents SDK Docs](https://platform.openai.com/docs/guides/agents)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Smolagents GitHub](https://github.com/huggingface/smolagents)
- [PydanticAI Documentation](https://ai.pydantic.dev/)
