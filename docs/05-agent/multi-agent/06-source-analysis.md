# 6. 源码分析

> 一句话理解：**主流 Multi-Agent 框架的核心差异在于“抽象层级”与“状态共享方式”——AutoGen 强调对话即编排，LangGraph 用图显式建模状态，CrewAI 用角色任务流程降低样板，OpenAI Agents SDK 用 Handoff 做轻量切换，CAMEL 用角色扮演数据集驱动，MetaGPT 则用 SOP 模拟软件公司**。

## 分析对象选择

| 项目 | 仓库/文档 | 定位 | 分析重点 |
|---|---|---|---|
| **AutoGen** | [microsoft.github.io/autogen](https://microsoft.github.io/autogen/stable/) | 多 Agent 对话编排先驱 | Conversation、GroupChat、CodeExecutor、状态共享 |
| **LangGraph multi-agent** | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/concepts/multi_agent/) | 生产级图编排 | StateGraph、多 Agent 节点、条件边、checkpoint |
| **CrewAI** | [docs.crewai.com](https://docs.crewai.com/) | 角色驱动的低样板框架 | Agent、Task、Process、Crew、工具委派 |
| **OpenAI Agents SDK handoffs** | [openai.github.io/openai-agents-python](https://openai.github.io/openai-agents-python/handoffs/) | 厂商原生轻量切换 | Agent、handoff、context 传递 |
| **CAMEL** | [docs.camel-ai.org](https://docs.camel-ai.org/) | 角色扮演与数据合成 | RolePlaying、Agent Society、数据飞轮 |
| **MetaGPT** | [docs.deepwisdom.ai](https://docs.deepwisdom.ai/main/Main%20Guide/) | 软件公司模拟 | Role、Action、Environment、SOP |

> 注：开源项目迭代较快，本节基于 2026 年中主流分支结构进行分析，具体 API 可能随版本微调。

## AutoGen

AutoGen 把 Multi-Agent 抽象成“对话（Conversation）”。

### 核心抽象

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat

assistant = AssistantAgent(name="coder", llm_config=llm_config)
user_proxy = UserProxyAgent(name="user", code_execution_config={"work_dir": "coding"})

groupchat = GroupChat(agents=[assistant, user_proxy], messages=[], max_round=12)
```

- **ConversableAgent**：所有 Agent 的基类，能收发消息。
- **GroupChat**：多 Agent 的群聊容器，内置发言人选择策略。
- **UserProxyAgent**：代表人类用户，可执行代码。

### 关键设计

1. **发言人选择（speaker selection）**：GroupChat 通过 LLM 或规则决定下一轮谁发言。
2. **代码执行器**：Agent 生成代码后，UserProxyAgent 可在沙箱中执行并返回结果。
3. **状态即消息历史**：共享状态主要体现在 `messages` 列表，所有 Agent 可见。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 对话式抽象直观 | 复杂状态管理较弱 |
| 内置代码执行与 human-in-the-loop | 学习曲线较陡 |
| 社区生态丰富 | 大型群聊容易发散 |

## LangGraph multi-agent

LangGraph 把 Multi-Agent 表达为“图”，每个 Agent 是一个节点，共享 State。

### 核心抽象

```python
from langgraph.graph import StateGraph, END

def agent_a(state): ...
def agent_b(state): ...

def router(state):
    return "agent_b" if state["needs_b"] else END

graph = StateGraph(State)
graph.add_node("agent_a", agent_a)
graph.add_node("agent_b", agent_b)
graph.add_conditional_edges("agent_a", router)
app = graph.compile()
```

### 关键设计

1. **显式 State**：所有 Agent 读写同一个 State，状态变更可审计。
2. **条件边**：通过函数决定下一步流转到哪个 Agent。
3. **Checkpoint**：支持中断/恢复/time-travel，适合长时任务。
4. **Handoff 模式**：LangGraph 官方文档把 handoff 实现为 Agent 节点返回 `goto` 指令。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 状态显式、可持久化 | 学习曲线陡 |
| 适合复杂生产工作流 | 简单任务样板代码多 |
| 可观测强 | 依赖 LangChain 生态 |

## CrewAI

CrewAI 把 Multi-Agent 抽象为“团队（Crew）= 角色（Agent）+ 任务（Task）+ 流程（Process）”。

### 核心抽象

```python
from crewai import Agent, Task, Crew

researcher = Agent(role="研究员", goal="收集资料", backstory="...")
writer = Agent(role="撰稿人", goal="生成报告", backstory="...")

task1 = Task(description="搜索主题", agent=researcher)
task2 = Task(description="撰写报告", agent=writer, context=[task1])

crew = Crew(agents=[researcher, writer], tasks=[task1, task2], process=Process.sequential)
result = crew.kickoff()
```

### 关键设计

1. **角色驱动**：Agent 必须定义 role、goal、backstory。
2. **任务依赖**：Task 通过 `context` 声明前置任务输出。
3. **流程**：支持 sequential、hierarchical、consensual 等协作模式。
4. **工具委派**：Agent 可以把子任务动态委派给其他 Agent 或工具。

### 优点与局限

| 优点 | 局限 |
|---|---|
| API 简洁、样板少 | 复杂状态管理不如 LangGraph |
| 角色概念清晰 | 高度依赖 Prompt 工程 |
| 适合快速原型 | 生产级可观测需自行集成 |

## OpenAI Agents SDK handoffs

OpenAI Agents SDK 的 Multi-Agent 能力主要通过 handoff 实现：一个 Agent 可以把对话交给另一个 Agent。

### 核心抽象

```python
from agents import Agent, Runner

triage = Agent(
    name="Triage",
    instructions="判断问题类型并转交",
    handoffs=[sales, support],
)

result = await Runner.run(triage, "我想退款")
```

### 关键设计

1. **handoff 是特殊 tool call**：模型决定切换到哪个 Agent，Runner 负责更新当前 Agent 与 instructions。
2. **context 透传**：对话历史在切换时保留。
3. **轻量**：几行代码即可实现客服分诊等场景。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 极简 API | 深度绑定 OpenAI 生态 |
| 原生支持 guardrails/tracing | 复杂 Multi-Agent 编排能力有限 |
| 适合快速落地 | 缺乏显式共享状态 |

## CAMEL

CAMEL 强调“角色扮演（Role-Playing）”与数据合成。

### 核心抽象

```python
from camel.agents import ChatAgent
from camel.societies import RolePlaying

society = RolePlaying(
    task_prompt="设计一个股票交易机器人",
    user_role_name="量化交易员",
    assistant_role_name="Python 工程师",
)
```

### 关键设计

1. **角色扮演数据集**：通过两个 Agent 对话自动生成任务导向的数据。
2. **Agent Society**：支持更复杂的多 Agent 社会结构。
3. **数据飞轮**：对话数据可用于训练与评估。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 数据合成能力强 | 工程化部署相对薄弱 |
| 角色扮演研究价值高 | 不适合直接做生产编排 |

## MetaGPT

MetaGPT 用软件公司 SOP 模拟 Multi-Agent 协作。

### 核心抽象

```python
from metagpt.roles import Architect, Engineer, ProductManager
from metagpt.team import Team

team = Team()
team.hire([ProductManager(), Architect(), Engineer(n_borg=3)])
team.run_project(idea="写一个命令行 Todo 应用")
```

### 关键设计

1. **Role + Action + Environment**：每个角色有固定动作集，在共享环境中读写文档。
2. **SOP 编码**：把软件开发的流程（需求 → PRD → 架构 → 代码 → 测试）硬编码进系统。
3. **共享环境**：所有 Agent 通过文件/文档共享状态。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 对软件开发场景极强 | 通用性受限 |
| SOP 可解释性强 | 流程固化，难做动态调整 |

## 综合对比

| 维度 | AutoGen | LangGraph | CrewAI | OpenAI SDK | CAMEL | MetaGPT |
|---|---|---|---|---|---|---|
| 核心抽象 | 对话/群聊 | 状态图 | 角色+任务+团队 | Agent/Runner/Handoff | 角色扮演 | Role/Action/SOP |
| 状态共享 | 消息历史 | 显式 State | Task context | 对话历史 | 共享环境 | 文档/文件 |
| 调度方式 | 发言人选择 | 图边 | Process/委派 | Handoff tool | 角色协商 | SOP 流程 |
| 持久化 | 较弱 | 强 | 较弱 | 较弱 | 较弱 | 较弱 |
| 可观测 | 中等 | 强 | 较弱 | 强（OpenAI） | 较弱 | 中等 |
| 最佳场景 | 探索性对话 | 复杂生产工作流 | 快速原型 | OpenAI 快速落地 | 数据合成 | 软件开发 |

## 共同模式总结

无论哪种框架，生产级 Multi-Agent 都需要解决四个问题：

1. **角色与能力如何声明**（Role/Skill/Agent）。
2. **状态在哪里共享**（消息历史、State、Blackboard、文档）。
3. **下一步由谁执行**（Coordinator、条件边、发言人选择、Handoff）。
4. **结果如何聚合与终止**（Aggregator、终止条件、冲突解决）。

## 本章小结

AutoGen、LangGraph、CrewAI、OpenAI Agents SDK、CAMEL、MetaGPT 代表了 Multi-Agent 的六种设计取向：对话编排、图状态编排、角色任务流、轻量 Handoff、角色扮演数据合成、SOP 模拟。理解它们的抽象层级与状态共享方式，有助于在自己的场景中做出合理选型。

**参考来源**

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [AutoGen Paper](https://arxiv.org/abs/2308.08155)
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [CAMEL Documentation](https://docs.camel-ai.org/)
- [MetaGPT Documentation](https://docs.deepwisdom.ai/main/Main%20Guide/)
- [MetaGPT Paper](https://arxiv.org/abs/2308.00352)
