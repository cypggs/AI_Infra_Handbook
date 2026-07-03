"""Tiny FastAPI LLM-like service with OpenTelemetry traces and Prometheus metrics."""

from __future__ import annotations

import os
import random
import time

from fastapi import FastAPI, Query
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

RESOURCE = Resource(attributes={"service.name": "chat-service"})
trace.set_tracer_provider(TracerProvider(resource=RESOURCE))
# Default to an in-memory exporter for a self-contained demo/tests.
# Set OTEL_EXPORTER_OTLP_ENDPOINT for OTLP, or AI_SRE_CONSOLE_TRACES=1 for console output.
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    _exporter = OTLPSpanExporter()
elif os.getenv("AI_SRE_CONSOLE_TRACES"):
    _exporter = ConsoleSpanExporter()
else:
    _exporter = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(_exporter))

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total chat requests",
    ["model", "status"],
)
CHAT_DURATION = Histogram(
    "chat_request_duration_seconds",
    "Chat request duration",
    ["model"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


def _simulate_llm(query: str) -> tuple[str, int, float, bool]:
    """Return (answer, tokens, latency_seconds, success)."""
    tokens = max(5, min(50, len(query) + random.randint(-3, 15)))
    # Simulate ~5% error rate and variable latency.
    success = random.random() > 0.05
    latency = random.uniform(0.01, 0.4) if success else random.uniform(0.5, 1.2)
    answer = f"answer to '{query}' ({tokens} tokens)"
    return answer, tokens, latency, success


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/chat")
def chat(q: str = Query(..., description="User query")) -> dict[str, object]:
    model = "gpt-mini"
    start = time.perf_counter()
    answer, tokens, latency, success = _simulate_llm(q)

    with trace.get_tracer(__name__).start_as_current_span("llm.generate") as span:
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.usage.output_tokens", tokens)
        span.set_attribute("gen_ai.request.temperature", 0.7)
        if not success:
            span.set_status(trace.Status(trace.StatusCode.ERROR, "generation failed"))
            span.record_exception(Exception("simulated generation failure"))

    duration = time.perf_counter() - start
    CHAT_DURATION.labels(model=model).observe(duration)
    status = "success" if success else "error"
    CHAT_REQUESTS.labels(model=model, status=status).inc()

    return {
        "answer": answer,
        "model": model,
        "tokens": tokens,
        "success": success,
        "latency_ms": round(duration * 1000, 2),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
