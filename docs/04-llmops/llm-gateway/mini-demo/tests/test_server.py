import json

import pytest

from llm_gateway_mini.config import (
    GatewayConfig,
    ModelConfig,
    ProviderConfig,
    RateLimitConfig,
)
from llm_gateway_mini.providers import BaseProvider
from llm_gateway_mini.server import GatewayApp


class DummyProvider(BaseProvider):
    def __init__(self, cfg: ProviderConfig):
        super().__init__(cfg, sleep=lambda x: None)
        self.responses = 0

    def chat_completions(self, request: dict) -> dict:
        self.responses += 1
        return {
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}}
            ],
            "usage": {},
        }


def make_app(strategy: str = "round_robin") -> GatewayApp:
    providers = {
        "fast": DummyProvider(ProviderConfig(name="fast", type="openai", endpoint="", latency_ms=5)),
        "slow": DummyProvider(ProviderConfig(name="slow", type="openai", endpoint="", latency_ms=10)),
    }
    config = GatewayConfig(
        providers={k: v.config for k, v in providers.items()},
        models={"model-a": ModelConfig(alias="model-a", providers=["fast", "slow"])},
        rate_limits={"default": RateLimitConfig(requests_per_minute=60, burst=10)},
    )
    return GatewayApp(config, providers=providers, router_strategy=strategy)


def test_health():
    app = make_app()
    assert app.handle_health()["status"] == "ok"


def test_models():
    app = make_app()
    data = app.handle_models()
    assert any(m["id"] == "model-a" for m in data["data"])


def test_chat_completions_routes_and_records_metrics():
    app = make_app()
    body = json.dumps(
        {"model": "model-a", "messages": [{"role": "user", "content": "hi"}]}
    ).encode()
    resp = app.handle_chat_completions("tenant-A", body)
    assert resp["provider"] in ("fast", "slow")
    assert resp["choices"][0]["message"]["content"] == "ok"
    assert app.metrics.requests.get('provider="fast",model="model-a",tenant="tenant-A"') > 0 or \
           app.metrics.requests.get('provider="slow",model="model-a",tenant="tenant-A"') > 0


def test_chat_completions_missing_model():
    app = make_app()
    body = json.dumps({"messages": []}).encode()
    resp = app.handle_chat_completions("tenant-A", body)
    assert resp["status"] == 400


def test_chat_completions_unknown_model():
    app = make_app()
    body = json.dumps({"model": "unknown", "messages": []}).encode()
    resp = app.handle_chat_completions("tenant-A", body)
    assert resp["status"] == 404


def test_chat_completions_rate_limit():
    app = make_app()
    body = json.dumps(
        {"model": "model-a", "messages": [{"role": "user", "content": "hi"}]}
    ).encode()
    for _ in range(10):
        resp = app.handle_chat_completions("tenant-A", body)
        assert resp.get("status") != 429

    resp = app.handle_chat_completions("tenant-A", body)
    assert resp["status"] == 429


def test_chat_completions_fallback():
    class FailingProvider(BaseProvider):
        def chat_completions(self, request: dict) -> dict:
            raise RuntimeError("always fails")

    providers = {
        "bad": FailingProvider(ProviderConfig(name="bad", type="openai", endpoint="")),
        "good": DummyProvider(ProviderConfig(name="good", type="openai", endpoint="")),
    }
    config = GatewayConfig(
        providers={k: v.config for k, v in providers.items()},
        models={"model-a": ModelConfig(alias="model-a", providers=["bad", "good"])},
        rate_limits={"default": RateLimitConfig(requests_per_minute=60, burst=10)},
    )
    app = GatewayApp(config, providers=providers)
    body = json.dumps(
        {"model": "model-a", "messages": [{"role": "user", "content": "hi"}]}
    ).encode()
    resp = app.handle_chat_completions("tenant-A", body)
    assert resp["provider"] == "good"


def test_metrics_endpoint_output():
    app = make_app()
    body = json.dumps(
        {"model": "model-a", "messages": [{"role": "user", "content": "hi"}]}
    ).encode()
    app.handle_chat_completions("tenant-A", body)
    text = app.handle_metrics()
    assert "gateway_requests_total" in text
    assert "gateway_latency_ms" in text
