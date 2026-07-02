# Reflection Mini Demo

A CPU-runnable, pure-Python miniature of a **Reflection** agent loop. It
demonstrates a generator, critic, evaluator, scoped workspace, observer, and
revision loop — without GPUs or external LLM keys.

## Design

The demo is split into small, focused modules:

| Module | Responsibility |
|--------|----------------|
| `llm_client.py` | `MockLLMClient`: deterministic, rule-based LLM responses |
| `workspace.py` | `Workspace`: scoped shared state with history |
| `generator.py` | `GeneratorAgent`: produces drafts from a request |
| `critic.py` | `CriticAgent`: critiques each draft |
| `evaluator.py` | `Evaluator`: scores draft/critique pairs |
| `reflection_loop.py` | `RevisionLoop`: generate → critique → evaluate → revise |
| `observer.py` | `Observer`: structured event recording and trace rendering |
| `demo.py` | Entry script: "Explain Agent Reflection" scenario |

### Why a deterministic LLM client?

Real reflection systems call LLM providers that require API keys, network
access, and non-deterministic outputs. The demo uses a rule-based client so
that:

- The code runs on any CPU with zero setup.
- Tests are deterministic and reproducible.
- The core concepts (critique-driven revision, pass/fail evaluation) remain clear.

In production, replace `MockLLMClient` with a real LLM client.

## Install

```bash
cd docs/05-agent/reflection/mini-demo
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m reflection_mini.demo
```

or, after installing the package:

```bash
reflection-demo
```

The demo runs a reflection loop that:

1. **Generator** writes a vague first draft.
2. **Critic** reports that the draft lacks an example and is too abstract.
3. **Evaluator** scores the draft as a fail.
4. **Generator** revises with a concrete example.
5. **Critic** and **Evaluator** mark the revision as a pass.
6. **RevisionLoop** finalizes the draft.

## Run tests

```bash
pytest tests/ -v
```

## Programmatic usage

```python
from reflection_mini.critic import CriticAgent
from reflection_mini.evaluator import Evaluator
from reflection_mini.generator import GeneratorAgent
from reflection_mini.llm_client import MockLLMClient
from reflection_mini.observer import Observer
from reflection_mini.reflection_loop import RevisionLoop
from reflection_mini.workspace import Workspace

llm_client = MockLLMClient()
loop = RevisionLoop(
    generator=GeneratorAgent(llm_client),
    critic=CriticAgent(llm_client),
    evaluator=Evaluator(llm_client),
    workspace=Workspace(),
    observer=Observer(),
    max_iterations=3,
    score_threshold=1.0,
)
result = loop.run("Explain Agent Reflection in one paragraph")
print(result["workspace"]["final_draft"])
```

## Mini demo vs. a real framework

| Capability | Mini demo | Real framework (e.g., Self-Refine, Reflexion) |
|------------|-----------|-----------------------------------------------|
| LLM | Rule-based mock | OpenAI / Anthropic / local models |
| State storage | In-memory workspace | Database / vector store |
| Evaluation | Deterministic scorer | LLM-as-judge or learned reward model |
| Stopping rule | Score threshold | Convergence / budget / learned policy |
| Observability | stdout trace | OpenTelemetry / structured logs |

This project is intentionally small: it shows the concepts and control flow so
readers can understand how reflection works before adopting a heavier system.

## License

Same as the parent project: CC-BY-SA-4.0.
