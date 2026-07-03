# OpenAI Mini Demo

A tiny OpenAI-compatible Chat Completions API server demonstrating model routing, token-bucket rate limiting, and streaming SSE responses.

## Install

```bash
cd docs/09-case-study/openai/mini-demo
pip install -e ".[dev]"
```

## Run

```bash
uvicorn openai_mini.server:app --port 8000
```

## Test endpoints

Non-streaming:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-demo" \
  -d '{
    "model": "gpt-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Streaming:

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-demo" \
  -d '{
    "model": "gpt-mini",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

## Test

```bash
pytest tests/ -q
```
