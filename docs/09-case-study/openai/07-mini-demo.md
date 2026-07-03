# Mini Demo

本章介绍 `docs/09-case-study/openai/mini-demo/` 中的迷你示例。它实现一个 OpenAI-compatible 的推理服务入口，演示模型路由、速率限制与流式响应。

## 场景

一个名为 `openai-mini` 的 FastAPI 服务提供 `/v1/chat/completions` 接口：

- 兼容 OpenAI Chat Completions API 的请求/响应格式。
- 按 `model` 字段路由到不同“模型”（gpt-mini / gpt-large）。
- 使用 token bucket 限流，防止单 key 打爆服务。
- 支持 `stream=true` 的 SSE 流式返回。
- 模拟模型生成，无需外部 LLM key。

## 目录结构

```text
mini-demo/
├── pyproject.toml
├── README.md
├── openai_mini/
│   ├── __init__.py
│   ├── server.py        # FastAPI + 路由 + 限流 + SSE
│   ├── router.py        # 模型路由逻辑
│   ├── limiter.py       # Token bucket 限流器
│   └── generator.py     # 模拟生成器
└── tests/
    ├── __init__.py
    ├── test_server.py
    ├── test_router.py
    └── test_limiter.py
```

## 安装

```bash
cd docs/09-case-study/openai/mini-demo
pip install -e ".[dev]"
```

## 运行服务

```bash
uvicorn openai_mini.server:app --port 8000
```

## 测试接口

非流式：

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-demo" \
  -d '{
    "model": "gpt-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

流式：

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

## 测试

```bash
pytest tests/ -q
```

## 关键代码片段

### 1. Token Bucket 限流

```python
class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
```

### 2. 模型路由

```python
def pick_model(requested: str) -> str:
    if requested in MODELS:
        return requested
    if requested.startswith("gpt-"):
        return "gpt-mini"
    raise ValueError(f"unsupported model: {requested}")
```

### 3. SSE 流式响应

```python
async def stream_response(model: str, prompt: str):
    for token in generator.generate(model, prompt):
        yield f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"
    yield "data: [DONE]\n\n"
```

## 与生产系统的差异

| 方面 | Mini Demo | OpenAI 生产 |
|---|---|---|
| 模型 | 模拟生成 | 真实 GPT-4 / GPT-4o / o1 |
| 部署 | 单进程 | 全球多区域 GPU 集群 |
| 限流 | 内存 token bucket | 分布式 quota + tier 系统 |
| 路由 | 简单字符串匹配 | 负载、容量、延迟多维调度 |
| 安全 | 无 | Moderation、Guardrails、审计 |
| 可观测 | 无 | trace、metrics、SLO |

## 扩展练习

1. 把限流器换成 Redis -backed 分布式限流。
2. 增加基于请求复杂度的模型选择（例如按输入长度选择大小模型）。
3. 增加请求/响应日志与 Prometheus metrics。
4. 接入真实的小型本地模型（如 llama.cpp）替换模拟生成。

## 小结

Mini Demo 展示了 OpenAI API 入口的最小控制面：**认证 → 限流 → 路由 → 生成 → 流式返回**。它是理解大规模 LLM Gateway 的动手沙盒。
