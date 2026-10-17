# 6. 源码分析

> 一句话理解：**主流 Multi-Agent 框架的核心差异在于“抽象层级”与“状态共享方式”——AutoGen 系强调对话即编排，LangGraph 用图显式建模状态，CrewAI 用角色任务流程降低样板，OpenAI Agents SDK 用 Handoff 做轻量切换，Google ADK 用代码优先的工作流 Agent 组合子 Agent，CAMEL 用角色扮演数据集驱动，MetaGPT 则用 SOP 模拟软件公司**。

## 分析对象选择

| 项目 | 仓库/文档 | 定位 | 分析重点 |
|---|---|---|---|
| **AutoGen / AG2 / Microsoft Agent Framework** | [microsoft.github.io/autogen](https://microsoft.github.io/autogen/stable/) / [docs.ag2.ai](https://docs.ag2.ai/) / [learn.microsoft.com/agent-framework](https://learn.microsoft.com/agent-framework/) | 多 Agent 对话编排先驱及其两条演进线 | GroupChat、AG2 Network hub、MAF Workflows |
| **LangGraph multi-agent** | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/concepts/multi_agent/) | 生产级图编排，1.0 已 GA | StateGraph、Supervisor/Swarm 库、Command + active_agent |
| **CrewAI** | [docs.crewai.com](https://docs.crewai.com/) | 角色驱动的低样板框架 | Agent、Task、Process、Flows、工具委派 |
| **OpenAI Agents SDK** | [openai.github.io/openai-agents-python](https://openai.github.io/openai-agents-python/) | 厂商原生轻量切换（Swarm 的正式继任） | Agent、Runner、Handoff、Guardrails、Tracing |
| **Google ADK** | [adk.dev](https://adk.dev/agents/multi-agents/) | Google 代码优先多 Agent 框架，A2A 原生 | LlmAgent、Workflow Agents、session.state |
| **CAMEL** | [docs.camel-ai.org](https://docs.camel-ai.org/) | 角色扮演与数据合成 | RolePlaying、Agent Society、数据飞轮 |
| **MetaGPT** | [docs.deepwisdom.ai](https://docs.deepwisdom.ai/main/Main%20Guide/) | 软件公司模拟 | Role、Action、Environment、SOP |

> 注：开源项目迭代极快，本节基于 2026 年 10 月主流分支状态分析。近两年 Multi-Agent 框架格局发生了数次洗牌（AutoGen 归档、AG2 v1.0 重写、LangGraph 1.0 GA、ADK 2.0/MAF 1.0 发布），选型时务必核实项目当前状态，不要只看 star 数。

## AutoGen、AG2 与 Microsoft Agent Framework

AutoGen 把 Multi-Agent 抽象成“对话（Conversation）”，是这一领域的先驱，但它的故事在 2025-2026 年分成了三条线：

- **AutoGen（原库）**：已进入维护尾声，2026 年 10 月正式 **归档（archived）**——微软在仓库公告中明确不再提供 bug 修复、安全修复与新功能，仓库仅作历史参考，最终版本停在 v0.7.5（2025 年 9 月）。
- **AG2**：原创始团队离开微软后创建的分叉（Apache 2.0），保持活跃。v1.0 是一次彻底重写——用 Network hub + 类型化 channel 取代了 GroupChat 与 ConversableAgent，不向后兼容；经典 API 保留在 `ag2-classic` 包中。2026 年 10 月时已迭代到 v1.2.x。
- **Microsoft Agent Framework（MAF）**：微软官方继任者，合并 AutoGen 与 Semantic Kernel，2026 年 4 月发布 1.0 GA（production-ready 承诺），提供 typed-graph Workflows、Handoff 编排、原生 MCP/A2A 支持，覆盖 Python 与 .NET（Go 版处于 public preview）。2026 年 7 月起又发布 `agent-framework-hosting-a2a` 包，可直接把 Agent / Workflow 以 A2A 服务端点对外暴露（原生 Agent Card 生成、技能发现）；2026 年 10 月 Python 版已迭代到 1.22.x。

### AutoGen 核心抽象（历史版本）

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

### 演进启示

| 版本线 | 核心变化 | 启示 |
|---|---|---|
| AG2 v1.0 | Network hub + 类型化 channel 取代自由群聊 | 自由对话式编排难以治理，向显式通信拓扑收敛 |
| MAF 1.0 | Workflows（typed graph）+ Handoff + MCP/A2A | 企业级编排 = 确定性工作流 + LLM 决策点 + 标准协议 |

## LangGraph multi-agent

LangGraph 把 Multi-Agent 表达为“图”，每个 Agent 是一个节点，共享 State。2025 年 10 月 17 日 LangGraph 1.0 GA（与 LangChain 1.0 同日发布），把 durable execution（自动持久化、崩溃恢复）变成内置能力，成为生产级 Agent 编排的主流选项之一（Uber、LinkedIn、Klarna 等有公开采用）。此后持续高频迭代，2026 年 10 月已到 1.2.x（如 1.2.16），durable execution 能力持续增强（例如跨主机崩溃的 durable error-handler resume）。

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
app = graph.compile(checkpointer=checkpointer)
```

### 关键设计

1. **显式 State**：所有 Agent 读写同一个 State，状态变更可审计。
2. **条件边**：通过函数决定下一步流转到哪个 Agent。
3. **Checkpoint / Durable Execution**：支持中断、恢复、time-travel，进程重启后可从上次状态继续。
4. **Handoff 原语**：Agent 节点返回 `Command(goto=..., update={"active_agent": ...})` 移交控制权。
5. **Supervisor 与 Swarm 独立库**：`langgraph-supervisor` 提供集中式 Manager，`langgraph-swarm` 提供去中心化 handoff（需配合 checkpointer 记住当前活跃 Agent）。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 状态显式、可持久化 | 学习曲线陡 |
| 适合复杂生产工作流 | 简单任务样板代码多 |
| 可观测强、生态成熟 | 依赖 LangChain 生态 |

## CrewAI

CrewAI 把 Multi-Agent 抽象为“团队（Crew）= 角色（Agent）+ 任务（Task）+ 流程（Process）”，2025-2026 年持续高频迭代，当前为 1.15.x 系列（2026 年 10 月）；v1.14 起移除了 LangChain 依赖独立运行（官方 README 已将其定位为 standalone 框架），并补齐了运行时 checkpointing、可插拔 memory/RAG 后端。

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
3. **Process**：支持 sequential、hierarchical、consensual 等协作模式。
4. **Flows**：事件驱动的状态机，支持条件路由与持久化状态，弥补 Crew 在复杂分支流程上的不足。
5. **工具委派**：Agent 可以把子任务动态委派给其他 Agent 或工具。

### 优点与局限

| 优点 | 局限 |
|---|---|
| API 简洁、样板少 | 复杂状态管理不如 LangGraph |
| 角色概念清晰、迭代活跃 | 高度依赖 Prompt 工程 |
| Flows 支持事件驱动流程 | 深度自定义需理解其内部约定 |

## OpenAI Agents SDK（Swarm 的正式继任）

OpenAI 早期开源的 Swarm 只是一个教学级实验（Agents + Handoffs + Routines，官方明确“不用于生产”）。2025 年其能力被正式的 **OpenAI Agents SDK** 继承并大幅扩展：Guardrails（输入/输出/工具校验）、内置 Tracing（OTel 兼容）、Sessions 状态管理。SDK 保持活跃迭代，2026 年 10 月已发布到 v0.24.x。

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
2. **context 透传**：对话历史在切换时保留；可用 input filter 控制移交时携带的上下文量。
3. **Guardrails + Tracing 内置**：生产所需的护栏与可观测开箱即用。
4. **轻量**：几行代码即可实现客服分诊等场景。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 极简 API、上手最快 | 深度绑定 OpenAI 生态 |
| 原生 guardrails/tracing | 复杂状态机编排能力弱于 LangGraph |
| 适合快速落地 | 缺乏显式共享状态 |

## Google ADK

Google ADK（Agent Development Kit）是 Google 的代码优先 Agent 框架，2025 年 4 月在 Google Cloud Next 发布、同年 5 月发布 Python v1.0.0；**2026 年 5 月 19 日 Python 版 2.0.0 GA**，随后 Go 2.0（2026 年 6 月）、TypeScript 2.0（2026 年 8 月）相继 GA，2026 年 10 月 Python 版已迭代到 v2.12.x。ADK 与 A2A 协议绑定：同一套 Agent 定义既能进程内编排，也能通过 A2A 暴露给外部 Agent。

### 核心抽象

```python
from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent

researcher = LlmAgent(name="researcher", model="gemini-2.5-flash", instruction="...")
writer = LlmAgent(name="writer", model="gemini-2.5-pro", instruction="...")

crew = SequentialAgent(
    name="content_team",
    sub_agents=[ParallelAgent(sub_agents=[researcher_a, researcher_b]), writer],
)
```

### 关键设计

1. **LlmAgent 为基本推理单元**：负责推理、工具调用与下一步决策。
2. **Workflow Agents 为确定性编排**：`SequentialAgent` / `ParallelAgent` / `LoopAgent` 本身不含 LLM，只做子 Agent 的有序、并发、循环调度，形成树状 Agent 结构。
3. **session.state 共享状态**：子 Agent 通过 `output_key` 把结果写入会话状态，下游读取。
4. **A2A 原生**：Agent 可直接以 A2A 服务端点暴露；ADK 的 Event Compaction（事件压缩）用 LLM 把旧会话事件压缩为摘要状态而非直接截断——Google 官方公布的基准称长会话 token 消耗降低约 38%、延迟降低约 18%（该数字为官方口径，尚缺少独立第三方复现）。

### 优点与局限

| 优点 | 局限 |
|---|---|
| 编排确定性与 LLM 决策分离得干净 | 生态集中在 Google Cloud / Gemini |
| 多语言（Python/Java/Go/TS） | 动态图能力弱于 LangGraph |
| 与 A2A 协议天然一体 | 国内网络与合规接入成本高 |

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

| 维度 | AutoGen/AG2 | LangGraph | CrewAI | OpenAI SDK | Google ADK | MetaGPT/CAMEL |
|---|---|---|---|---|---|---|
| 核心抽象 | 对话/Network | 状态图 | 角色+任务+Flow | Agent/Runner/Handoff | LlmAgent+Workflow | Role/Action/SOP、角色扮演 |
| 状态共享 | 消息历史/channel | 显式 State | Task context/session.state | 对话历史/Sessions | session.state | 文档/共享环境 |
| 调度方式 | 发言人选择/hub | 图边 + 条件路由 | Process/Flow 事件 | Handoff tool | 编排 Agent 组合子 Agent | SOP/角色协商 |
| 持久化 | 较弱（AG2/MAF 较强） | 强（durable execution） | 中（checkpointing） | 中（Sessions） | 中（session 服务） | 较弱 |
| 可观测 | 中 | 强 | 中 | 强（内置 tracing） | 强（Google Cloud 集成） | 较弱 |
| 最佳场景 | 对话式探索/遗留系统 | 复杂生产工作流 | 快速原型/业务流程 | OpenAI 生态快速落地 | GCP 生态/A2A 互联 | 软件开发/数据合成 |

## 共同模式总结

无论哪种框架，生产级 Multi-Agent 都需要解决四个问题：

1. **角色与能力如何声明**（Role/Skill/Agent，对外即 Agent Card）。
2. **状态在哪里共享**（消息历史、State、Blackboard、session.state、文档）。
3. **下一步由谁执行**（Coordinator、条件边、发言人选择、Handoff、编排 Agent）。
4. **结果如何聚合与终止**（Aggregator、终止条件、冲突解决）。

另一个 2026 年的共识：**框架间的边界正在溶解**。LangGraph、CrewAI、ADK、MAF 都已支持 A2A/MCP，一个 LangGraph 编排的 Agent 可以把任务 handoff 给通过 A2A 暴露的第三方 Agent。选型时越来越应关注协议兼容性而非框架私有特性。

## 本章小结

AutoGen/AG2、Microsoft Agent Framework、LangGraph、CrewAI、OpenAI Agents SDK、Google ADK、CAMEL、MetaGPT 代表了 Multi-Agent 的多种设计取向。2025-2026 年的主线是：AutoGen 系完成“社区分叉 + 官方重写”的更替，LangGraph 以 1.0 GA 确立图编排的生产地位，OpenAI 与 Google 分别用 Agents SDK 和 ADK 把 handoff 与 A2A 做成厂商标准，而 A2A v1.0 让不同框架的 Agent 第一次可以跨组织协作。理解它们的抽象层级与状态共享方式，有助于在自己的场景中做出合理选型。

**参考来源**

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [AutoGen Paper](https://arxiv.org/abs/2308.08155)
- [AG2 文档](https://docs.ag2.ai/)
- [Microsoft Agent Framework 文档](https://learn.microsoft.com/agent-framework/)
- [AutoGen 仓库归档公告](https://github.com/microsoft/autogen)
- [Microsoft Agent Framework Releases](https://github.com/microsoft/agent-framework/releases)
- [AG2 Releases](https://github.com/ag2ai/ag2/releases)
- [ADK Python Releases](https://github.com/google/adk-python/releases)
- [OpenAI Agents Python Releases](https://github.com/openai/openai-agents-python/releases)
- [CrewAI Releases](https://github.com/crewAIInc/crewAI/releases)
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [LangGraph v1 发布说明](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [CrewAI Documentation](https://docs.crewai.com/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [Google ADK — Multi-Agent Systems](https://adk.dev/agents/multi-agents/)
- [A2A Protocol 文档](https://a2a-protocol.dev/)
- [CAMEL Documentation](https://docs.camel-ai.org/)
- [MetaGPT Documentation](https://docs.deepwisdom.ai/main/Main%20Guide/)
- [MetaGPT Paper](https://arxiv.org/abs/2308.00352)
