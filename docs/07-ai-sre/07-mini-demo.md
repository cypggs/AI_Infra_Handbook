# Mini Demo

本章介绍 `docs/07-ai-sre/mini-demo/` 中的 AI SRE 迷你示例。它演示如何为一个模拟的 LLM 服务添加 OpenTelemetry trace、Prometheus metrics，并基于指标计算 SLO burn rate。

## 场景

一个名为 `chat-service` 的 FastAPI 应用提供 `/chat` 接口：

- 模拟 LLM 生成延迟与 token 用量。
- 自动记录 HTTP trace。
- 暴露 `/metrics` 供 Prometheus 抓取。
- 附带脚本 `slo_demo.py` 计算可用性 SLO 与 burn rate。

## 目录结构

```text
mini-demo/
├── pyproject.toml
├── README.md
├── ai_sre_mini/
│   ├── __init__.py
│   ├── service.py        # FastAPI + OTel + Prometheus
│   └── slo.py            # SLO / burn rate 计算
├── tests/
│   ├── __init__.py
│   ├── test_service.py
│   └── test_slo.py
```

## 安装

```bash
cd docs/07-ai-sre/mini-demo
pip install -e ".[dev]"
```

## 运行服务

```bash
uvicorn ai_sre_mini.service:app --port 8000
```

## 测试接口

```bash
curl "http://127.0.0.1:8000/chat?q=hello"
```

返回示例：

```json
{
  "answer": "hello (tokens=15)",
  "model": "gpt-mini",
  "tokens": 15,
  "latency_ms": 23.4
}
```

## 查看指标

```bash
curl -s http://127.0.0.1:8000/metrics | grep chat_requests
```

你会看到类似：

```text
chat_requests_total{model="gpt-mini",status="success"} 12.0
chat_requests_total{model="gpt-mini",status="error"} 1.0
chat_request_duration_seconds_bucket{le="0.1",model="gpt-mini"} ...
```

## SLO Burn Rate 演示

```bash
python -m ai_sre_mini.slo
```

脚本会拉取 `/metrics`，计算可用性 SLI、SLO 剩余预算与 burn rate。

## 关键代码片段

### 1. 服务初始化与埋点

```python
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram

resource = Resource(attributes={"service.name": "chat-service"})
trace.set_tracer_provider(TracerProvider(resource=resource))
# Default in-memory exporter; set OTEL_EXPORTER_OTLP_ENDPOINT or AI_SRE_CONSOLE_TRACES=1 to switch.
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(InMemorySpanExporter())
)

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

CHAT_REQ = Counter("chat_requests_total", "Chat requests", ["model", "status"])
CHAT_LAT = Histogram("chat_request_duration_seconds", "Chat latency", ["model"])
```

### 2. 自定义 LLM span

```python
with trace.get_tracer(__name__).start_as_current_span("llm.generate") as span:
    span.set_attribute("gen_ai.request.model", model)
    span.set_attribute("gen_ai.usage.output_tokens", tokens)
    span.set_attribute("gen_ai.request.temperature", 0.7)
    ...
```

### 3. SLO 计算

```python
def burn_rate(error_rate: float, slo_error_budget: float) -> float:
    if slo_error_budget <= 0:
        return float("inf")
    return error_rate / slo_error_budget
```

## 测试

```bash
pytest tests/ -q
```

测试覆盖：

- `/chat` 接口返回正确字段。
- `/metrics` 暴露且包含自定义指标。
- SLO/burn rate 计算正确。

## 与生产系统的差异

| 方面 | Mini Demo | 生产系统 |
|---|---|---|
| Exporter | In-memory by default; optional OTLP/Console | OTLP to Collector/Jaeger/Grafana |
| Metrics storage | In-process | Prometheus/Thanos |
| Sampling | 100% | Head/tail sampling |
| PII | 未脱敏 | 关闭内容捕获或脱敏 |
| Alerting | 无 | Alertmanager/PagerDuty |
| AIOps | 无 | 动态基线、根因分析 |

## 扩展练习

1. 把 ConsoleSpanExporter 换成 OTLPSpanExporter，接入 OpenTelemetry Collector。
2. 增加 token 成本指标，并配置 cost-per-request SLO。
3. 用 Prometheus + Alertmanager 实现 burn rate 告警。
4. 增加一个模拟的“幻觉”错误类型，并记录到 span status。
5. 用 Grafana 画出 TTFT、ITL、token 用量、burn rate 仪表板。

## 小结

Mini Demo 展示了 AI SRE 的最小闭环：**instrument → expose metrics → compute SLO**。它是理解后续生产实践章节的动手沙盒。
