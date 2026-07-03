# Anthropic Mini Demo

A tiny demo reproducing two of Anthropic's most distinctive engineering ideas:

1. **Prompt caching** — a faithful model of Claude's prefix-cache semantics: writes happen only at breakpoints, reads look backward up to 20 blocks, 5-minute / 1-hour TTL, workspace isolation, and cost accounting with the official pricing multipliers (read 0.1x, 5m write 1.25x, 1h write 2x).
2. **Constitutional critique-revise** — a deterministic, rule-based version of the Constitutional AI supervised-learning phase (critique then revise against a small constitution).

It exposes an Anthropic-style `/v1/messages` endpoint using `x-api-key` auth and returning `usage` with `cache_read_input_tokens` / `cache_creation_input_tokens`.

## Install

```bash
cd docs/09-case-study/anthropic/mini-demo
pip install -e ".[dev]"
```

## Run

```bash
uvicorn anthropic_mini.server:app --port 8000
```

## Test endpoints

Plain request (no caching):

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-demo" \
  -d '{
    "model": "claude-haiku-mini",
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "What is RAG?"}]
  }'
```

With automatic prompt caching (top-level `cache_control`). Send it twice: the second response shows `cache_read_input_tokens > 0`.

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-demo" \
  -d '{
    "model": "claude-haiku-mini",
    "max_tokens": 64,
    "cache_control": {"type": "ephemeral"},
    "system": "You are a helpful, honest, harmless assistant.",
    "messages": [{"role": "user", "content": "Summarize RAG in one line."}]
  }'
```

## Test

```bash
pytest tests/ -q
```
