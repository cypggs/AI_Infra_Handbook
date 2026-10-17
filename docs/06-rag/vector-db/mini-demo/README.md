# Vector DB Mini Demo

A tiny, CPU-runnable vector search and embedding-infrastructure demo that
implements the three workhorse index families (brute force, IVF, a simplified
HNSW graph), two classic quantizers (SQ / PQ) and a deterministic toy
embedding service — no GPU, no network, no external model weights.

## Structure

- `vector_db_mini/metric.py` — l2 / inner-product / cosine distances
- `vector_db_mini/quantize.py` — ScalarQuantizer + ProductQuantizer (seeded, reproducible)
- `vector_db_mini/index.py` — FlatIndex / IVFFlatIndex / HNSWIndex (simplified single-layer graph)
- `vector_db_mini/embed.py` — ToyEmbeddingServer: md5 feature-hashing bag-of-words encoder with batching semantics
- `vector_db_mini/demo.py` — six end-to-end scenarios (`run_demo()`)
- `tests/` — 69 deterministic pytest tests

## Install

```bash
cd docs/06-rag/vector-db/mini-demo
pip install -e ".[dev]"
```

## Run

```bash
vector-db-demo
# or
python -m vector_db_mini.demo
```

## Test

```bash
pytest tests/ -q
```

## Notes

- All randomness is fixed-seed: recalls and reconstruction errors are
  reproducible; only wall-clock latencies vary between runs.
- The HNSW implementation is intentionally simplified: one graph layer,
  beam search with `ef`, and a deterministic mutual-link heuristic
  (reverse links are added while a node's degree stays under `2M`). It is
  a teaching model, not a replacement for hnswlib/FAISS.
- The embedding server is a semantic stand-in for TEI / Infinity-style
  services (batching, normalization, truncation, request counting) — the
  vectors come from feature hashing, not a neural network.
