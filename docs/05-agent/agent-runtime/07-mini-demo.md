# 7. 工程实践：Mini Agent Runtime

> 一句话理解：这个 Mini Demo 用纯 Python 实现一个最小可用的 ReAct-style Agent Runtime，展示任务解析、工具注册、function calling、记忆、状态机、护栏、观测与恢复。

## Demo 设计

真实 Agent Runtime（OpenAI Agents SDK、LangGraph、CrewAI 等）通常包含大量抽象与集成；为了在不依赖外部 LLM key、不依赖 GPU 的情况下讲清楚核心机制，本 Demo 采用纯 Python 模拟：

- **LLM Client**：一个可配置的 mock，根据 prompt 内容决定返回 `thought` 还是 `tool_calls`，模拟 function calling 响应。
- **Tool Registry**：用 `@tool` 装饰器注册 Python 函数，自动生成 JSON Schema。
- **Executor**：调用工具并捕获结果，教学版沙箱做超时与异常隔离。
- **Runtime Loop**：实现标准的 ReAct 循环，含最大迭代次数保护。
- **Memory**：维护会话级 message history；支持简单截断/摘要。
- **State**：用状态机记录 `idle/planning/acting/observing/done/error`。
- **Guardrails**：输入检查、工具调用次数限制、路径白名单、高风险操作需 HITL。
- **Observer**：记录 trace event，输出树形执行路径。
- **Planner**：简单任务分解示例。

## 目录结构

```text
docs/05-agent/agent-runtime/mini-demo/
├── README.md
├── pyproject.toml
├── agent_runtime_mini/
│   ├── __init__.py
│   ├── runtime.py         # AgentRuntime：ReAct 主循环
│   ├── llm_client.py      # MockLLMClient：模拟 function calling
│   ├── tool_registry.py   # @tool 装饰器、JSON Schema、调用分发
│   ├── executor.py        # ToolExecutor：安全执行工具
│   ├── memory.py          # WorkingMemory：上下文管理
│   ├── state.py           # SessionState：状态机
│   ├── guardrails.py      # Guardrails：多层策略检查
│   ├── observer.py        # TraceObserver：事件与 span 记录
│   ├── planner.py         # SimplePlanner：任务分解
│   └── demo.py            # 入口演示
└── tests/
    ├── test_runtime.py
    ├── test_tool_registry.py
    ├── test_executor.py
    ├── test_memory.py
    ├── test_guardrails.py
    └── test_observer.py
```

## 核心能力一览

| 能力 | 文件 | 说明 |
|---|---|---|
| ReAct 循环 | `runtime.py` | thought → action → observation 循环，含 max_steps |
| 模拟 LLM | `llm_client.py` | 根据 prompt 返回 tool_calls 或最终答案 |
| 工具注册 | `tool_registry.py` | `@tool` 装饰器 + 自动 JSON Schema |
| 工具执行 | `executor.py` | 超时、异常隔离、权限前置检查 |
| 记忆 | `memory.py` | messages 列表 + 截断策略 |
| 状态 | `state.py` | 会话状态机 |
| 护栏 | `guardrails.py` | 输入/工具前置/输出/资源限制 |
| 观测 | `observer.py` | event + span 记录 |
| 规划 | `planner.py` | 简单子目标分解 |

## 快速运行

### 1. 安装依赖

```bash
cd docs/05-agent/agent-runtime/mini-demo
pip install -e ".[dev]"
```

### 2. 运行 Demo

```bash
python -m agent_runtime_mini.demo
```

Demo 会依次执行：

1. 数学计算任务（调用 `calculator`）。
2. 搜索摘要任务（调用 `search` 并生成最终答案）。
3. 被护栏拦截的任务（敏感词/越权）。
4. 需要 HITL 确认的写文件任务（测试模式自动通过）。

### 3. 运行测试

```bash
pytest tests/ -v
```

### 4. 作为库使用

```python
from agent_runtime_mini.runtime import AgentRuntime
from agent_runtime_mini.llm_client import MockLLMClient
from agent_runtime_mini.tool_registry import default_tool_registry
from agent_runtime_mini.guardrails import Guardrails
from agent_runtime_mini.observer import TraceObserver

runtime = AgentRuntime(
    llm_client=MockLLMClient(),
    tools=default_tool_registry(),
    guardrails=Guardrails(max_tool_calls=5, forbidden_keywords=["password"]),
    observer=TraceObserver(),
)
answer, observer = runtime.run("计算 25 * 4 + 10", session_id="demo-1")
print(answer)
print(observer.render())
```

## 关键代码片段

### 工具注册

```python
from agent_runtime_mini.tool_registry import tool

@tool(description="计算数学表达式，例如 '25 * 4 + 10'")
def calculator(expr: str) -> str:
    return str(eval(expr))
```

### ReAct 循环

```python
def run(self, task: str, session_id: str) -> Tuple[str, TraceObserver]:
    self.guardrails.check_input(task)
    state.transition(State.PLANNING)
    subgoals = self.planner.plan(task)
    memory.add_system_prompt(self._build_system_prompt())
    memory.add_user_message(task)
    for iteration in range(1, self.max_iterations + 1):
        state.transition(State.ACTING)
        response = self.llm_client.generate(memory.get_messages())
        choice = response["choices"][0]
        if choice["finish_reason"] == "stop":
            state.transition(State.DONE)
            return choice["message"].get("content", ""), self.observer
        if choice["finish_reason"] == "tool_calls":
            for tool_call in choice["message"].get("tool_calls", []):
                state.transition(State.OBSERVING)
                self.guardrails.check_tool_call(tool_call, call_count)
                approved = self.guardrails.request_approval(tool_call)
                result = self.executor.execute(tool_call, context={"approved": approved})
                memory.add_tool_message(tool_call["id"], str(result))
    return f"Max iterations reached ({self.max_iterations})", self.observer
```

### 状态机

```python
class SessionState:
    IDLE = "idle"
    PLANNING = "planning"
    ACTING = "acting"
    OBSERVING = "observing"
    DONE = "done"
    ERROR = "error"
    WAITING_FOR_HUMAN = "waiting_for_human"
```

## 测试结果示例

```text
tests/test_executor.py::test_execute_success PASSED
tests/test_executor.py::test_execute_wraps_exception PASSED
tests/test_executor.py::test_execute_timeout PASSED
tests/test_guardrails.py::test_forbidden_keyword_in_input PASSED
tests/test_guardrails.py::test_allowed_input PASSED
tests/test_guardrails.py::test_max_tool_calls PASSED
tests/test_guardrails.py::test_forbidden_path PASSED
tests/test_guardrails.py::test_allowed_path PASSED
tests/test_guardrails.py::test_blocked_path_not_in_allowlist PASSED
tests/test_guardrails.py::test_always_approve_write PASSED
tests/test_guardrails.py::test_denied_write PASSED
tests/test_memory.py::test_add_and_retrieve_messages PASSED
tests/test_memory.py::test_token_truncation_drops_oldest_non_system PASSED
tests/test_memory.py::test_tool_messages PASSED
tests/test_observer.py::test_record_events PASSED
tests/test_observer.py::test_render_contains_events PASSED
tests/test_runtime.py::test_math_task PASSED
tests/test_runtime.py::test_search_task PASSED
tests/test_runtime.py::test_blocked_by_input_guardrail PASSED
tests/test_runtime.py::test_max_iterations PASSED
tests/test_tool_registry.py::test_default_schemas PASSED
tests/test_tool_registry.py::test_calculator PASSED
tests/test_tool_registry.py::test_calculator_rejects_unsafe_code PASSED
tests/test_tool_registry.py::test_search PASSED
tests/test_tool_registry.py::test_dispatch PASSED
tests/test_tool_registry.py::test_write_file_requires_approval PASSED
tests/test_tool_registry.py::test_write_file_with_approval PASSED

============================== 27 passed in 0.11s ==============================
```

## 生产差异说明

| 能力 | Demo 实现 | 生产系统 |
|---|---|---|
| LLM | Mock deterministic | OpenAI / Anthropic / vLLM / Gateway |
| 工具执行 | 同进程函数调用 | 沙箱/容器/独立进程 |
| 记忆 | 内存 | Redis / 向量 DB / 长期记忆 |
| 状态 | 内存 | Postgres / Checkpoint Store |
| 护栏 | 简单规则 | 多模态内容安全、RBAC |
| 可观测 | stdout trace | OpenTelemetry / LangSmith |
| HITL | 自动通过 | 人工审批系统 |

## 本章小结

Mini Demo 展示了 Agent Runtime 的最小可行实现：通过 ReAct 循环把 LLM、工具、记忆、状态、护栏、观测串成一条流水线。虽然代码量不大，但已经覆盖了生产 Runtime 的 80% 核心概念。推荐阅读 [`mini-demo/README.md`](./mini-demo/README.md) 获取完整运行说明。

**参考来源**

- [OpenAI Agents SDK Quick Start](https://platform.openai.com/docs/guides/agents)
- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [LangGraph Quick Start](https://langchain-ai.github.io/langgraph/tutorials/introduction/)
