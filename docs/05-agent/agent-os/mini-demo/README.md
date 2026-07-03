# Agent OS Mini Demo

A tiny, CPU-runnable demonstration of operating-system-like abstractions for
running and coordinating multiple agents. It uses only the Python standard
library and requires no external API keys or network calls.

## Scenario

A `CoordinatorAgent` is asked to compute `(a + b) * c` for `a=2`, `b=3`,
`c=4`. It delegates subtasks to two sandboxed workers:

1. `AdderAgent` computes `a + b`.
2. `MultiplierAgent` multiplies the intermediate result by `c`.

The kernel spawns processes, the scheduler picks ready processes in round-robin
order, the sandbox enforces a strict `calculate` tool allowlist and a per-worker
call budget, and the workspace plus message bus carry intermediate results back
to the coordinator.

## Project Layout

```
mini-demo/
├── README.md
├── pyproject.toml
├── agent_os_mini/
│   ├── __init__.py
│   ├── kernel.py         # spawn, schedule, terminate, registry
│   ├── process.py        # AgentProcess lifecycle and state
│   ├── scheduler.py      # round-robin / priority schedulers
│   ├── sandbox.py        # capability/policy enforcement
│   ├── workspace.py      # shared + per-process blackboard
│   ├── message_bus.py    # inbox/outbox IPC
│   ├── observer.py       # event trace
│   └── demo.py           # run_demo() entry point
└── tests/
    └── ...               # pytest coverage
```

## Running the Demo

Install in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run the demo CLI:

```bash
agent-os-demo
```

Or from Python:

```python
from agent_os_mini.demo import run_demo
run_demo()
```

## Running Tests

```bash
pytest tests/ -q
```

## Design Notes

- **No external LLM SDKs**: every agent is a deterministic Python function.
- **Sandbox policy**: each worker may only call the `calculate` tool and is
  limited to two calls. Exceeding the budget raises `PolicyViolation`.
- **Scheduler**: the default is round-robin; a priority scheduler is also
  provided for comparison.
- **Determinism**: execution order and output are fully deterministic.

## License

This demo is part of the AI Infra Handbook.
