# RAG Mini Demo

A tiny, CPU-runnable Retrieval-Augmented Generation (RAG) pipeline that answers questions from a small set of documents about the fictional **Acme Corp**.

This demo uses only the Python standard library and contains no external LLM SDKs or ML libraries.

## Structure

- `rag_mini/documents.py` — sample documents and a simple chunker with overlap and metadata
- `rag_mini/embedder.py` — deterministic embedder and keyword index (no external models)
- `rag_mini/vector_store.py` — in-memory vector store with cosine similarity and metadata filtering
- `rag_mini/retriever.py` — dense, keyword (BM25-like), and hybrid retrieval with RRF
- `rag_mini/reranker.py` — simple score-based reranker
- `rag_mini/generator.py` — mock LLM that answers from retrieved context
- `rag_mini/demo.py` — `run_demo()` entry point

## Install

```bash
cd /Users/case/AI_Infra_Handbook/docs/06-rag/mini-demo
pip install -e ".[dev]"
```

## Run

```bash
rag-demo
```

Or from Python:

```python
from rag_mini.demo import run_demo
run_demo()
```

## Test

```bash
pytest tests/ -q
```

## Design Notes

- **No network calls**: everything is computed locally.
- **Deterministic output**: embeddings and answers are reproducible for the same inputs.
- **Clean separation**: each pipeline stage can be tested independently.
