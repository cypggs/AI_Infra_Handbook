# AI SRE Mini Demo

A tiny FastAPI service instrumented with OpenTelemetry traces and Prometheus metrics, plus a simple SLO burn-rate calculator.

## Install

```bash
cd docs/07-ai-sre/mini-demo
pip install -e ".[dev]"
```

## Run

```bash
uvicorn ai_sre_mini.service:app --port 8000
```

To see traces printed to the console, run with `AI_SRE_CONSOLE_TRACES=1`.
To send traces to an OTLP Collector, set `OTEL_EXPORTER_OTLP_ENDPOINT`.

## Test endpoints

```bash
curl "http://127.0.0.1:8000/chat?q=hello"
curl -s http://127.0.0.1:8000/metrics | grep chat_requests
```

## SLO demo

```bash
python -m ai_sre_mini.slo
```

## Test

```bash
pytest tests/ -q
```
