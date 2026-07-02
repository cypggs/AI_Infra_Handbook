# Agent Runtime Mini Demo

A CPU-runnable, pure-Python miniature of an **Agent Runtime**. It demonstrates a
ReAct loop, tool/function calling, working memory, session state management,
input/output guardrails, trace observability, and recovery without GPUs or
external LLM keys.

## Design

The demo is split into small, focused modules:

| Module | Responsibility |
|--------|----------------|
| `runtime.py` | `AgentRuntime`: state-machine ReAct loop (idle -> planning -> acting -> observing -> done/error) |
| `llm_client.py` | `MockLLMClient`: deterministic function-calling responses driven by prompt keywords |
| `tool_registry.py` | `@tool` decorator, JSON-Schema generation from type hints, dispatch |
| `executor.py` | `ToolExecutor`: runs tool calls with timeout isolation and exception wrapping |
| `memory.py` | `WorkingMemory`: conversation history with simple token-count truncation |
| `state.py` | Session state machine and transitions |
| `guardrails.py` | Safety limits: max tool calls, forbidden keywords, path restrictions, human approval for writes |
| `observer.py` | `TraceObserver`: record events/spans and render a simple trace tree |
| `planner.py` | `SimplePlanner`: decompose a task into subgoals |
| `demo.py` | Entry script: runs math, search, and guardrail-blocked tasks |

### ReAct loop

1. A task enters the runtime.
2. The planner turns it into subgoals.
3. Memory is populated with the system prompt, tool schemas, and user task.
4. The runtime calls the mock LLM, which returns either a `tool_calls` response or a `stop` answer.
5. If the LLM asks for a tool, the runtime dispatches it through `ToolExecutor`, records the observation, and loops.
6. Guardrails are checked before tool execution; if triggered, the task transitions to `error`.
7. A `max_iterations` guardrail prevents infinite loops.

### Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `calculator(expr)` | Evaluate a math expression safely | Uses `ast` arithmetic only |
| `search(query)` | Mock web search | Returns canned text for known queries |
| `read_file(path)` | Read from an in-memory filesystem | Restricted to allowed paths |
| `write_file(path, content)` | Write to an in-memory filesystem | Requires human approval via guardrails |

## Install

```bash
cd docs/05-agent/agent-runtime/mini-demo
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m agent_runtime_mini.demo
```

or, after installing the package:

```bash
agent-runtime-demo
```

The demo runs three tasks:

1. A math task (`"What is 25*4+10?"`).
2. A search task (`"Search for the current president of the United States"`).
3. A task blocked by guardrails (`"Write a secret to /etc/passwd"`).

It prints each trace tree, the final answer, and the final session state.

## Programmatic usage

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
answer, trace = runtime.run("What is 25*4+10?", session_id="demo-1")
print(answer)
print(trace.render())
```

## Run tests

```bash
pytest tests/
```

## Mini demo vs. a real framework

| Capability | Mini demo | Real framework (e.g., LangGraph, AutoGen, OpenAI Agents SDK) |
|------------|-----------|--------------------------------------------------------------|
| LLM | Deterministic mock | Real OpenAI / Anthropic / local model endpoint |
| Tool calling | Native Python decorator + JSON Schema | Provider SDK, code interpreter, hosted actions |
| Planning | Simple subgoal splitter | Multi-agent orchestration, plan replay, replanning |
| Memory | In-memory working history | Vector stores, persistent thread memory, RAG |
| State | Single-session state machine | Distributed state, multi-agent state graphs |
| Guardrails | Keyword/path/approval checks | Policy engines, PII detectors, model-based moderation |
| Observability | In-memory event tree | OpenTelemetry, LangSmith, Weights & Biases |
| Recovery | Exception isolation + timeout | Retry queues, human-in-the-loop escalation |
| Deployment | Single process | Horizontally scalable, containerized services |

This project is intentionally small: it shows the concepts and control flow so
readers can understand how a production agent runtime behaves before adopting a
heavier system.
