# Multi-Agent Mini Demo

A CPU-runnable, pure-Python miniature of a **Multi-Agent** system. It
demonstrates agents, a message bus, a shared blackboard, deterministic skill
calling, handoff and round-robin coordination, and trace observability —
without GPUs or external LLM keys.

## Design

The demo is split into small, focused modules:

| Module | Responsibility |
|--------|----------------|
| `message.py` | `Message` dataclass and `MessageType` enum |
| `bus.py` | `MessageBus`: pub/sub message delivery |
| `blackboard.py` | `Blackboard`: scoped shared workspace |
| `agent.py` | `Agent`: role, instructions, skill registry, inbox |
| `llm_client.py` | `MockLLMClient`: deterministic, rule-based decisions |
| `skills.py` | Reusable skills: research, draft, review, finalize, handoff |
| `coordinator.py` | `Coordinator`: `handoff` and `round_robin` execution modes |
| `observer.py` | `Observer`: structured event recording and trace rendering |
| `demo.py` | Entry script: blog-writing task with a full agent team |

### Why a deterministic LLM client?

Real multi-agent systems use LLM providers that require API keys, network
access, and non-deterministic outputs. The demo uses a rule-based client so
that:

- The code runs on any CPU with zero setup.
- Tests are deterministic and reproducible.
- The core concepts (agent roles, handoffs, shared state) remain clear.

In production, replace `MockLLMClient` with a real LLM client.

## Install

```bash
cd docs/05-agent/multi-agent/mini-demo
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m multi_agent_mini.demo
```

or, after installing the package:

```bash
multi-agent-demo
```

The demo runs a handoff-mode blog-writing task:

1. **Coordinator** hands off to the researcher.
2. **Researcher** collects facts and writes them to the blackboard.
3. **Writer** produces a structured draft using the facts.
4. **Reviewer** adds review comments.
5. **Coordinator** finalizes the blog post.

## Run tests

```bash
pytest tests/ -v
```

## Programmatic usage

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

## Mini demo vs. a real framework

| Capability | Mini demo | Real framework (e.g., LangGraph, CrewAI, AutoGen) |
|------------|-----------|---------------------------------------------------|
| LLM | Rule-based mock | OpenAI / Anthropic / local models |
| Message transport | In-memory bus | Message queue / gRPC / WebSocket |
| Shared state | In-memory blackboard | Database / vector store |
| Observability | stdout trace | OpenTelemetry / structured logs |
| Fault tolerance | None by design | Retries, timeouts, circuit breakers |

This project is intentionally small: it shows the concepts and control flow so
readers can understand how a production multi-agent system behaves before
adopting a heavier system.

## License

Same as the parent project: CC-BY-SA-4.0.
