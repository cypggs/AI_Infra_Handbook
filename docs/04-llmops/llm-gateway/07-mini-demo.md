# 7. 工程实践：Mini Demo

> 一句话理解：这个 Mini Demo 用纯 Python + `http.server` 实现一个可运行的 LLM Gateway 骨架，覆盖配置加载、Provider 抽象、路由、负载均衡、限流、重试降级、认证、请求转换与 Prometheus 指标。

## Demo 设计

真实 LLM Gateway 通常由 LiteLLM、Envoy、Kong 等成熟系统承担；为了在不依赖外部二进制、不依赖 GPU 的情况下讲清楚核心机制，本 Demo 采用纯 Python 模拟：

- **上游 Provider**：用本地 mock server 模拟 OpenAI / vLLM / Triton 的响应。
- **Gateway**：基于 `http.server` 实现，向上暴露 OpenAI-compatible 接口。
- **配置驱动**：通过 `gateway_config.yaml` 定义 providers、models、routes、rate_limits。
- **测试覆盖**：`pytest` 验证路由、负载均衡、限流、重试、转换、端到端请求。

## 目录结构

```text
docs/04-llmops/llm-gateway/mini-demo/
├── README.md
├── pyproject.toml
├── llm_gateway_mini/
│   ├── __init__.py
│   ├── config.py          # 加载 gateway_config.yaml
│   ├── providers.py       # Provider 抽象与 mock 实现
│   ├── router.py          # model alias → provider 选择策略
│   ├── load_balancer.py   # 实例级选择算法
│   ├── rate_limiter.py    # Token Bucket 限流
│   ├── retry_fallback.py  # 重试、降级、熔断
│   ├── auth_middleware.py # API Key 校验
│   ├── transform.py       # 请求/响应转换
│   ├── metrics.py         # Prometheus 风格指标
│   ├── server.py          # http.server 入口
│   └── demo.py            # 一键启动 gateway + mock providers
└── tests/
    ├── test_router.py
    ├── test_load_balancer.py
    ├── test_rate_limiter.py
    ├── test_retry_fallback.py
    ├── test_transform.py
    └── test_server.py
```

## 核心能力一览

| 能力 | 文件 | 说明 |
|---|---|---|
| 配置加载 | `config.py` | YAML/JSON 配置，`provider`、`model`、`route`、`rate_limit` |
| Provider 抽象 | `providers.py` | `OpenAIProvider`、`vLLMProvider`、`TritonProvider` 统一接口 |
| 路由 | `router.py` | round-robin / weighted / least-latency / priority |
| 负载均衡 | `load_balancer.py` | provider 内实例选择 |
| 限流 | `rate_limiter.py` | 按 `api_key + model` 的 Token Bucket |
| 重试/降级/熔断 | `retry_fallback.py` | 指数退避、provider 链、熔断状态机 |
| 认证 | `auth_middleware.py` | key → tenant / allowed_models |
| 转换 | `transform.py` | OpenAI ↔ 上游内部格式 |
| 指标 | `metrics.py` | Counter / Histogram / Gauge，输出 Prometheus 文本 |
| 服务入口 | `server.py` | `/v1/models`、`/v1/chat/completions`、`/metrics`、`/health` |

## 快速运行

### 1. 安装依赖

```bash
cd docs/04-llmops/llm-gateway/mini-demo
pip install -e ".[dev]"
```

### 2. 启动 Gateway + Mock Providers

```bash
python -m llm_gateway_mini.demo
```

默认会启动：

- Mock OpenAI Provider：`http://127.0.0.1:9001`
- Mock vLLM Provider：`http://127.0.0.1:9002`
- Mock Triton Provider：`http://127.0.0.1:9003`
- Gateway：`http://127.0.0.1:8080`

### 3. 查看模型列表

```bash
curl -s http://127.0.0.1:8080/v1/models \
  -H "Authorization: Bearer sk-demo-key" | python -m json.tool
```

### 4. 调用 Chat Completions

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "你好"}]
  }' | python -m json.tool
```

### 5. 查看 Prometheus 指标

```bash
curl -s http://127.0.0.1:8080/metrics
```

示例输出片段：

```text
llm_gateway_requests_total{model="gpt-4o",provider="openai-mock",status="200"} 3.0
llm_gateway_latency_seconds_bucket{model="gpt-4o",provider="openai-mock",le="0.1"} 2.0
llm_gateway_tokens_total{model="gpt-4o",provider="openai-mock",type="input"} 30.0
llm_gateway_tokens_total{model="gpt-4o",provider="openai-mock",type="output"} 15.0
```

### 6. 运行测试

```bash
pytest tests/ -v
```

## 配置示例

`gateway_config.yaml`：

```yaml
keys:
  sk-demo-key:
    tenant: demo
    allowed_models: [gpt-4o, gpt-4o-mini, qwen-7b]
    rate_limit:
      requests_per_minute: 60

providers:
  openai-mock:
    kind: openai
    base_url: http://127.0.0.1:9001
    models: [gpt-4o, gpt-4o-mini]
    weight: 70
    priority: 1
    timeout: 10
  vllm-mock:
    kind: openai
    base_url: http://127.0.0.1:9002
    models: [gpt-4o-mini, qwen-7b]
    weight: 30
    priority: 2
    timeout: 10
  triton-mock:
    kind: triton
    base_url: http://127.0.0.1:9003
    models: [qwen-7b]
    priority: 3
    timeout: 10

models:
  gpt-4o:
    strategy: weighted
    providers: [openai-mock]
  gpt-4o-mini:
    strategy: weighted
    providers: [openai-mock, vllm-mock]
  qwen-7b:
    strategy: priority
    providers: [vllm-mock, triton-mock]

fallbacks:
  gpt-4o: gpt-4o-mini
```

## 关键代码片段

### Provider 抽象

```python
class Provider(ABC):
    @abstractmethod
    def chat_completions(self, request: dict) -> dict:
        ...

class OpenAIProvider(Provider):
    def __init__(self, name, base_url, timeout=10):
        self.name = name
        self.base_url = base_url
        self.timeout = timeout

    def chat_completions(self, request: dict) -> dict:
        # 模拟调用真实 OpenAI-compatible endpoint
        return call_openai_compatible(self.base_url, request)
```

### Token Bucket 限流

```python
class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_per_second = refill_per_second
        self.last_refill = time.monotonic()

    def allow(self, tokens: float = 1.0) -> bool:
        now = time.monotonic()
        delta = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + delta * self.refill_per_second)
        self.last_refill = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
```

### 路由选择

```python
class WeightedRouter:
    def __init__(self, providers):
        self.providers = providers
        self.total_weight = sum(p.weight for p in providers)

    def pick(self, context) -> Provider:
        r = random.uniform(0, self.total_weight)
        cumulative = 0
        for p in self.providers:
            cumulative += p.weight
            if r <= cumulative:
                return p
        return self.providers[-1]
```

### 重试降级

```python
def call_with_retry(gateway, request, model_config):
    errors = []
    for provider in pick_chain(model_config):
        for attempt in range(gateway.config.max_retries + 1):
            try:
                return provider.chat_completions(request)
            except RetryableError as e:
                errors.append(e)
                time.sleep(min(2 ** attempt, gateway.config.max_backoff))
    raise FallbackExhausted(errors)
```

## 测试结果示例

```text
tests/test_router.py::test_weighted PASSED
tests/test_load_balancer.py::test_round_robin PASSED
tests/test_rate_limiter.py::test_token_bucket PASSED
tests/test_retry_fallback.py::test_fallback PASSED
tests/test_transform.py::test_openai_to_triton PASSED
tests/test_server.py::test_chat_completions_e2e PASSED
```

## 生产差异说明

| 能力 | Demo 实现 | 生产系统 |
|---|---|---|
| 并发 | 单线程 http.server | ASGI（FastAPI/Go/Rust）+ 异步 upstream |
| 状态 | 内存 | Redis 共享限流/熔断状态 |
| 上游 | mock server | OpenAI / Azure / vLLM / Triton / SGLang |
| Secret | 明文配置 | Vault / KMS / 云 Secret Manager |
| 可观测 | 内存指标 | Prometheus + Grafana + OpenTelemetry |
| 安全 | 简单 key | OAuth2 / mTLS / PII 过滤 / 审计日志 |

## 本章小结

Mini Demo 展示了 LLM Gateway 的最小可行实现：通过配置驱动把 provider、路由、限流、重试、认证、转换、指标串成一条流水线。虽然代码量不大，但已经覆盖了生产网关的 80% 核心概念。推荐阅读 [`mini-demo/README.md`](./mini-demo/README.md) 获取完整运行说明。

**参考来源**

- [LiteLLM Proxy Quick Start](https://docs.litellm.ai/docs/proxy/quick_start)
- [Python http.server](https://docs.python.org/3/library/http.server.html)
- [Prometheus Exposition Formats](https://prometheus.io/docs/instrumenting/exposition_formats/)
