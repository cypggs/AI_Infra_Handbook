# LLM Gateway Mini Demo

A CPU-runnable, pure-Python miniature of an LLM Gateway. It demonstrates routing,
load balancing, rate limiting, retries with fallback, circuit breaking, request/response
transformation, and Prometheus-style metrics without requiring GPUs or external
gateway binaries.

## Design

The demo is split into small, focused modules:

| Module | Responsibility |
|--------|----------------|
| `config.py` | Load gateway configuration from YAML |
| `providers.py` | Mock `OpenAIProvider`, `vLLMProvider`, `TritonProvider` |
| `router.py` | Resolve a model alias to candidate providers and pick one |
| `load_balancer.py` | Selection algorithms: round-robin, weighted, least-latency, priority |
| `rate_limiter.py` | Token-bucket rate limiter keyed by tenant+model |
| `retry_fallback.py` | Retry policy, circuit breaker, fallback chain |
| `auth_middleware.py` | Bearer token -> tenant validation |
| `transform.py` | OpenAI request/respose normalization |
| `metrics.py` | Prometheus-style counters and histograms |
| `server.py` | `http.server` gateway wiring everything together |
| `demo.py` | Entry script: spins up 3 mock providers and sends concurrent traffic |

### Routing strategies

- `round_robin`: cycles through candidate providers per model
- `weighted`: random selection weighted by provider `weight`
- `least_latency`: picks the provider with the lowest moving-average latency
- `priority`: picks the provider with the lowest `priority` value

### Retry / fallback / circuit breaker

Each provider call is wrapped by `RetryPolicy` (exponential backoff). A per-provider
`CircuitBreaker` trips after 3 consecutive failures, enters an open state, then
half-opens after a cooldown. If the chosen provider fails, the `FallbackChain` tries
the next candidate.

## Install

```bash
cd docs/04-llmops/llm-gateway/mini-demo
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m llm_gateway_mini.demo
```

The demo writes a temporary YAML config with three mock providers (fast vLLM, slow
Triton, flaky OpenAI), starts the gateway on a random local port, and fires 20
concurrent requests. It prints routing decisions, rate-limit hits, fallback
behavior, and final Prometheus-style metrics.

## Run the server directly

```python
from llm_gateway_mini.config import load_config
from llm_gateway_mini.server import GatewayApp, make_server

config = load_config("config.yaml")
app = GatewayApp(config, router_strategy="weighted")
server = make_server(app, host="127.0.0.1", port=8080)
server.serve_forever()
```

Endpoints:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions` (OpenAI-compatible, requires `Authorization: Bearer <key>`)
- `GET /metrics`

Sample request:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-demo-123" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-mini", "messages": [{"role": "user", "content": "hello"}]}'
```

## Run tests

```bash
pytest tests/
```

## Mini demo vs. a real gateway

| Capability | Mini demo | Real gateway (e.g., LiteLLM, Kong, Envoy) |
|------------|-----------|-------------------------------------------|
| Upstream providers | Mock Python classes | Real OpenAI / vLLM / Triton endpoints |
| Transport | `http.server` | Production HTTP server / proxy |
| Auth | Static API key map | OAuth, JWT, RBAC, audit logs |
| Rate limiting | In-memory token bucket | Redis-backed, per-tenant quotas |
| Routing | Simple strategies | ML-based load prediction, cost-aware routing |
| Retries / fallback | In-process retry + circuit breaker | Distributed retry, queueing, dead-letter |
| Metrics | In-memory counters | Prometheus / Grafana, distributed tracing |
| Streaming | Not implemented | Full SSE streaming |
| Deployment | Single process | Horizontally scalable with config management |

This project is intentionally small: it shows the concepts and control flow so
readers can understand how a production gateway behaves before adopting a heavier
system.
