# Planning Mini Demo

A CPU-runnable, zero-external-API mini demo of an agent planning system. It demonstrates task decomposition, DAG-aware execution, observation tracing, and dynamic replanning through a travel-planning assistant scenario.

## Scenario

User task: **“帮我规划一次 北京→东京 3 天旅行，预算 8000 元”**

The system decomposes the task into tool calls, executes them in dependency order, observes a sold-out flight, triggers a replan, and finally produces an itinerary.

## Design

| Module | Responsibility |
|--------|----------------|
| `llm_client.py` | `MockLLMClient` returns deterministic plan/replan JSON based on keywords. |
| `plan.py` | `Step` / `Plan` dataclasses, topological ordering, cycle detection, ready-step selection. |
| `planner.py` | `TaskPlanner` converts LLM output into a validated `Plan` and checks tool names. |
| `tool_registry.py` | `ToolRegistry` registers and executes mock tools (`search_flight`, `search_hotel`, `calculate_total`, `check_policy`, `generate_itinerary`). |
| `executor.py` | `PlanExecutor` schedules ready steps, resolves argument references, captures observations, and drives replans. |
| `observer.py` | `Observer` records a chronological trace of execution events. |
| `replan_trigger.py` | `ReplanTrigger` decides whether to continue, replan, or fail. |
| `policy.py` | `Policy` enforces max steps, allowed tools, budget ceiling, and max replan count. |
| `demo.py` | `run_demo()` wires everything together and prints the plan, trace, and final result. |

## Install

```bash
cd /Users/case/AI_Infra_Handbook/docs/05-agent/planning/mini-demo
pip install -e ".[dev]"
```

## Run

```bash
python -m planning_mini.demo
```

Or, after install:

```bash
planning-demo
```

## Test

```bash
pytest tests/ -v
```

## Programmatic usage

```python
from planning_mini.demo import run_demo

result = run_demo()
print(result["success"])        # True
print(result["replan_count"])   # 1
```

You can also compose the components manually:

```python
from planning_mini.executor import PlanExecutor
from planning_mini.llm_client import MockLLMClient
from planning_mini.observer import Observer
from planning_mini.planner import TaskPlanner
from planning_mini.policy import Policy
from planning_mini.replan_trigger import ReplanTrigger
from planning_mini.tool_registry import ToolRegistry

registry = ToolRegistry()
registry.sold_out = True  # trigger the replan path

llm_client = MockLLMClient()
planner = TaskPlanner(llm_client, registry)
policy = Policy(
    max_steps=10,
    max_replans=2,
    budget_ceiling=8000.0,
    allowed_tools=set(registry.tools.keys()),
)
executor = PlanExecutor(registry, Observer(), ReplanTrigger(policy), policy, llm_client)

plan = planner.create_plan("帮我规划一次 北京→东京 3 天旅行，预算 8000 元")
result = executor.run(plan)
assert result["success"]
print(plan.steps[-1].result)
```

## Production differences

| Mini Demo | Production System |
|-----------|-------------------|
| `MockLLMClient` returns hard-coded JSON. | Real LLM (Claude / GPT / etc.) with structured output / JSON mode and prompt versioning. |
| Tools are in-memory Python functions with fixed outputs. | External API calls (flights, hotels, payments) with retries, timeouts, and circuit breakers. |
| `Observer` is a simple in-memory list. | Persistent telemetry (OpenTelemetry, logs, tracing) and structured event sinks. |
| Replanning uses a keyword-based rule. | LLM-based root-cause analysis and plan repair with cost estimation. |
| Single-process, sequential step execution. | Distributed task workers, parallel branches, and concurrency limits. |
| Policy is a small dataclass. | Centralized guardrails, RBAC, budget tracking, and audit trails. |
| No network or authentication. | AuthZ, secrets management, rate limiting, and sandboxing. |

## License

Same as the AI Infra Handbook project.
