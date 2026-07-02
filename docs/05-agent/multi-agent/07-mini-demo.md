# 7. 工程实践：Mini Multi-Agent

> 一句话理解：**这个 Mini Demo 用纯 Python、零外部 LLM key 实现一个最小可用的 Multi-Agent 协作系统，展示 Agent 角色与技能、Message Bus、Coordinator、共享 Blackboard、Observer 与 handoff / round-robin 两种调度模式**。

## Demo 设计

真实 Multi-Agent 框架（AutoGen、LangGraph、CrewAI 等）通常依赖外部 LLM、消息队列与持久化存储。为了在不调用外部模型、不依赖 GPU 的情况下讲清楚核心机制，本 Demo 采用纯 Python 模拟：

- **Agent**：具有 `name`、`role`、`instructions` 与 `skills` 的执行单元。
- **Skill**：可复用的 callable，例如 `search_facts`、`draft_section`、`review_draft`、`finalize_post`、`handoff_to`。
- **Message Bus**：内存消息总线，支持订阅、点对点发送与广播。
- **Blackboard**：共享状态区，Agent 按 key 读写中间结果，支持 `shared`/`readonly`/`private` 作用域。
- **MockLLMClient**：确定性规则驱动的“伪 LLM”，根据当前 Agent 的 role 与 Blackboard 状态决定下一步动作。
- **Coordinator**：编排器，支持 `handoff`（动态交接）与 `round_robin`（固定轮转）两种模式。
- **Observer**：记录跨 Agent 事件与 trace，便于教学与调试。

## 目录结构

```text
docs/05-agent/multi-agent/mini-demo/
├── README.md
├── pyproject.toml
├── multi_agent_mini/
│   ├── __init__.py
│   ├── agent.py            # Agent 类：role / skills / inbox
│   ├── message.py          # Message 数据类与类型枚举
│   ├── bus.py              # MessageBus：订阅 / 发送 / 广播 / 投递
│   ├── blackboard.py       # Blackboard：共享状态与作用域
│   ├── llm_client.py       # MockLLMClient：确定性决策
│   ├── skills.py           # 内置 skill：search_facts / draft / review / finalize / handoff
│   ├── coordinator.py      # Coordinator：handoff / round_robin 调度
│   ├── observer.py         # Observer：事件 / trace 记录与渲染
│   └── demo.py             # 入口：博客写作多 Agent 任务
└── tests/
    ├── __init__.py
    ├── test_agent.py
    ├── test_bus.py
    ├── test_blackboard.py
    ├── test_llm_client.py
    ├── test_skills.py
    ├── test_coordinator.py
    ├── test_observer.py
    └── test_demo.py
```

## 核心能力一览

| 能力 | 文件 | 说明 |
|---|---|---|
| Agent 抽象 | `agent.py` | role、instructions、skill 注册、收件箱、act |
| 消息传递 | `message.py` / `bus.py` | Message 数据类与内存 pub/sub |
| 共享状态 | `blackboard.py` | 按 key 读写，支持作用域 |
| 确定性决策 | `llm_client.py` | 根据 role + blackboard 状态返回 action |
| 可复用技能 | `skills.py` | research / draft / review / finalize / handoff |
| 调度编排 | `coordinator.py` | handoff 与 round_robin 两种模式 |
| 可观测 | `observer.py` | 结构化事件与 trace 渲染 |
| 入口演示 | `demo.py` | 博客写作任务：Coordinator → Researcher → Writer → Reviewer → Coordinator |

## 快速运行

### 1. 安装依赖

```bash
cd docs/05-agent/multi-agent/mini-demo
pip install -e ".[dev]"
```

### 2. 运行 Demo

```bash
python -m multi_agent_mini.demo
```

Demo 会执行一个 handoff 模式的博客写作任务：

1. **Coordinator** 接收用户请求，handoff 给 Researcher。
2. **Researcher** 收集事实并写入 `blackboard.facts`。
3. **Coordinator** handoff 给 Writer。
4. **Writer** 读取事实，产出 `blackboard.draft`。
5. **Coordinator** handoff 给 Reviewer。
6. **Reviewer** 审阅草稿，写入 `blackboard.review`。
7. **Coordinator** 发现产物齐全，调用 `finalize_post` 生成 `blackboard.final_post`。

### 3. 运行测试

```bash
pytest tests/ -v
```

### 4. 作为库使用

```python
from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.bus import MessageBus
from multi_agent_mini.coordinator import Coordinator
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.observer import Observer
from multi_agent_mini.demo import make_team

agents = make_team()
coordinator = Coordinator(
    agents=agents,
    mode="handoff",
    blackboard=Blackboard(),
    bus=MessageBus(),
    observer=Observer(),
    llm_client=MockLLMClient(),
)
result = coordinator.run("Write a short post about multi-agent systems.")
print(result["blackboard"]["final_post"])
```

## 关键代码片段

### 定义 Agent 与注册 Skill

```python
from multi_agent_mini.agent import Agent
from multi_agent_mini.skills import search_facts, draft_section

researcher = Agent(
    name="researcher",
    role="researcher",
    instructions="Collect key facts on the requested topic.",
)
researcher.register_skill("search_facts", search_facts)
```

### 确定性 Mock LLM 决策

```python
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.blackboard import Blackboard

llm = MockLLMClient()
blackboard = Blackboard()
print(llm.decide(researcher, blackboard, {}))
# {'action': 'skill', 'name': 'search_facts', 'args': {'query': 'multi-agent collaboration'}}
```

### 写入 Blackboard

```python
from multi_agent_mini.blackboard import Blackboard

bb = Blackboard()
bb.write("facts", "Multi-Agent improves modularity.", scope="shared")
print(bb.read("facts"))
```

### Coordinator 调度

```python
from multi_agent_mini.coordinator import Coordinator

coordinator = Coordinator(agents=agents, mode="handoff")
result = coordinator.run("Write a short blog post.")
print(result["turns"])       # 实际执行轮数
print(result["blackboard"])  # 最终黑板状态
```

## 测试结果示例

```text
tests/test_agent.py::test_register_skill PASSED
tests/test_agent.py::test_receive_message PASSED
tests/test_agent.py::test_act_runs_skill_decision PASSED
tests/test_agent.py::test_act_finalize PASSED
tests/test_agent.py::test_act_handoff PASSED
tests/test_blackboard.py::test_read_write PASSED
tests/test_blackboard.py::test_read_missing PASSED
tests/test_blackboard.py::test_delete PASSED
tests/test_blackboard.py::test_scopes_in_to_dict PASSED
tests/test_blackboard.py::test_invalid_scope_raises PASSED
tests/test_blackboard.py::test_keys_and_scope PASSED
tests/test_bus.py::test_subscribe_and_deliver PASSED
tests/test_bus.py::test_broadcast PASSED
tests/test_bus.py::test_unsubscribed_topic_is_not_delivered PASSED
tests/test_bus.py::test_history_tracks_delivered_messages PASSED
tests/test_coordinator.py::test_handoff_mode_completes PASSED
tests/test_coordinator.py::test_round_robin_mode_completes PASSED
tests/test_coordinator.py::test_invalid_mode_raises PASSED
tests/test_coordinator.py::test_run_records_trace_events PASSED
tests/test_demo.py::test_make_team_has_four_roles PASSED
tests/test_demo.py::test_run_demo_completes PASSED
tests/test_demo.py::test_run_demo_blackboard_contains_expected_keys PASSED
tests/test_llm_client.py::test_researcher_without_facts PASSED
tests/test_llm_client.py::test_writer_with_facts_no_draft PASSED
tests/test_llm_client.py::test_reviewer_with_draft_no_review PASSED
tests/test_llm_client.py::test_coordinator_when_all_ready PASSED
tests/test_llm_client.py::test_handoff_to_researcher_when_missing_facts PASSED
tests/test_llm_client.py::test_handoff_to_writer_when_missing_draft PASSED
tests/test_llm_client.py::test_handoff_to_reviewer_when_missing_review PASSED
tests/test_observer.py::test_record_events PASSED
tests/test_observer.py::test_render_contains_events PASSED
tests/test_observer.py::test_render_includes_timestamp PASSED
tests/test_skills.py::test_search_facts_writes_facts PASSED
tests/test_skills.py::test_draft_section_writes_draft PASSED
tests/test_skills.py::test_review_draft_writes_review PASSED
tests/test_skills.py::test_finalize_post_writes_final_post PASSED
tests/test_skills.py::test_handoff_to_records_next_agent PASSED

============================== 37 passed in 0.03s ==============================
```

## 生产差异说明

| 能力 | Demo 实现 | 生产系统 |
|---|---|---|
| LLM | 规则驱动的 MockLLMClient | OpenAI / Anthropic / vLLM / 自研 Gateway |
| Agent 执行 | 同进程函数调用 | 独立服务 / 容器 / Serverless |
| 消息总线 | 内存队列 | Redis Streams / RabbitMQ / Kafka / NATS |
| 共享黑板 | 内存 dict | Redis / Postgres + 事件溯源 / 向量存储 |
| 可观测 | stdout trace | OpenTelemetry / LangSmith / Prometheus |
| 权限隔离 | 无 | RBAC / namespace / 网络隔离 |
| 持久化 | 无 | Checkpoint / 消息落盘 |
| 容错 | 无 | 重试、超时、熔断、死信队列 |

## 本章小结

Mini Demo 展示了一个零外部依赖、纯 Python 的 Multi-Agent 协作系统：通过 `Agent`、`MessageBus`、`Blackboard`、`MockLLMClient`、`Coordinator` 与 `Observer`，实现了角色分工、消息传递、共享状态、确定性调度与可观测 trace。虽然 LLM 与消息中间件都是教学级实现，但已经覆盖了生产 Multi-Agent 系统的 80% 核心概念。推荐阅读 [`mini-demo/README.md`](./mini-demo/README.md) 获取完整运行说明，并在生产环境中替换为真实的 LLM 客户端、消息队列与持久化存储。

**参考来源**

- [AutoGen Documentation](https://microsoft.github.io/autogen/stable/)
- [LangGraph Multi-Agent Concepts](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
