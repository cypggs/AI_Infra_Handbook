# Agent Memory Mini Demo

A CPU-runnable, pure-Python miniature of an **Agent Memory** system. It demonstrates
working memory, short-term memory, long-term semantic memory, episodic memory,
procedural memory, deterministic embeddings, vector storage, hybrid retrieval,
summarization, and JSON persistence — without GPUs or external LLM keys.

## Design

The demo is split into small, focused modules:

| Module | Responsibility |
|--------|----------------|
| `embedder.py` | `DeterministicEmbedder`: hash-based n-gram embeddings, zero external deps |
| `vector_store.py` | `InMemoryVectorStore`: stores `(id, text, embedding, metadata)` records |
| `retriever.py` | `MemoryRetriever`: vector / keyword / hybrid retrieval |
| `working_memory.py` | `WorkingMemory`: current-session message buffer with budget truncation |
| `short_term_memory.py` | `ShortTermMemory`: recent turns and session summaries |
| `long_term_memory.py` | `LongTermMemory`: semantic facts and preferences |
| `episodic_memory.py` | `EpisodicMemory`: task episodes (goal, actions, outcome) |
| `procedural_memory.py` | `ProceduralMemory`: reusable patterns and few-shot examples |
| `summarizer.py` | `SimpleExtractiveSummarizer`: lightweight text compression |
| `storage.py` | `InMemoryStorage` / `JsonFileStorage`: pluggable persistence |
| `memory_service.py` | `MemoryService`: unified `remember` / `recall` / `consolidate` / `save` / `load` API |
| `demo.py` | Entry script: multi-session personalization demonstration |

### Why a deterministic embedder?

Real memory systems use neural embedding models (sentence-transformers, OpenAI
`text-embedding-3`, etc.). Those require model downloads, API keys, or GPUs. The
demo uses a deterministic hash-based embedder so that:

- The code runs on any CPU with zero setup.
- Tests are deterministic and reproducible.
- The core concepts (embedding → vector store → cosine retrieval) remain clear.

In production, replace `DeterministicEmbedder` with a real embedding model.

## Install

```bash
cd docs/05-agent/memory/mini-demo
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m agent_memory_mini.demo
```

or, after installing the package:

```bash
agent-memory-demo
```

The demo runs a multi-session scenario:

1. **Session A**: the user states a preference ("I like Python, dislike Java").
2. **Session B**: the user asks for a language recommendation; the Agent recalls
   the long-term preference and answers personally.
3. **Episodic memory**: a successful task episode is recorded and recalled for
   similar future tasks.
4. **Hybrid retrieval**: vector + keyword search over long-term facts.
5. **Summarization**: a long working memory is compressed into short-term memory.

## Run tests

```bash
pytest tests/ -v
```

## Programmatic usage

```python
from agent_memory_mini.memory_service import MemoryService

service = MemoryService()

# Remember a user preference
service.remember(
    memory_type="fact",
    content="用户 Alice 喜欢 Markdown 简洁周报",
    metadata={"user": "alice", "topic": "preference"},
)

# Recall relevant memories
results = service.recall("周报格式", memory_type="fact", top_k=3)
for r in results:
    print(r["text"])

# Persist to disk
service.save("memory.json")

# Restore in a new process
new_service = MemoryService()
new_service.load("memory.json")
```

## Mini demo vs. a real framework

| Capability | Mini demo | Real framework (e.g., Letta, LangGraph, Mem0) |
|------------|-----------|-----------------------------------------------|
| Embedder | Hash-based deterministic | sentence-transformers / OpenAI / Cohere |
| Vector store | In-memory | Chroma / Weaviate / Milvus / pgvector |
| Storage | Memory / JSON file | Postgres / Redis / MongoDB |
| Summarizer | Extractive | LLM-based generative |
| Privacy filter | Demo-level regex | PII detection + anonymization |
| Multi-tenancy | `metadata` isolation | Namespace / collection / physical isolation |
| Observability | stdout | OpenTelemetry / Prometheus |

This project is intentionally small: it shows the concepts and control flow so
readers can understand how a production agent memory system behaves before
adopting a heavier system.

## License

Same as the parent project: CC-BY-SA-4.0.
