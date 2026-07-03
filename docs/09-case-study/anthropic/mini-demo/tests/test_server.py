"""Tests for the Anthropic-style /v1/messages endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

import anthropic_mini.server as server_module
from anthropic_mini.server import app

client = TestClient(app)


def _base_request(system: str, user: str, workspace: str = "ws") -> dict:
    return {
        "model": "claude-opus-mini",
        "max_tokens": 64,
        "system": system,
        "workspace": workspace,
        "messages": [{"role": "user", "content": user}],
    }


def test_unauthorized_without_api_key() -> None:
    r = client.post("/v1/messages", json=_base_request("sys", "hi"))
    assert r.status_code == 401


def test_unauthorized_wrong_api_key() -> None:
    r = client.post(
        "/v1/messages", json=_base_request("sys", "hi"), headers={"x-api-key": "wrong"}
    )
    assert r.status_code == 401


def test_invalid_model_returns_400() -> None:
    body = _base_request("sys", "hi")
    body["model"] = "gpt-4"
    r = client.post("/v1/messages", json=body, headers={"x-api-key": "sk-demo"})
    assert r.status_code == 400


def test_basic_response_shape() -> None:
    r = client.post(
        "/v1/messages",
        json=_base_request("sys", "What is RAG?", workspace="shape"),
        headers={"x-api-key": "sk-demo"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "assistant"
    assert body["content"][0]["type"] == "text"
    assert isinstance(body["content"][0]["text"], str) and body["content"][0]["text"]
    usage = body["usage"]
    for key in (
        "input_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "output_tokens",
    ):
        assert key in usage


def test_automatic_caching_hits_on_second_request() -> None:
    headers = {"x-api-key": "sk-demo"}
    sys_prompt = "You are a helpful, honest, harmless assistant." * 20  # > minimum length
    payload = {
        "model": "claude-haiku-mini",
        "max_tokens": 64,
        "cache_control": {"type": "ephemeral"},
        "system": sys_prompt,
        "workspace": "auto",
        "messages": [{"role": "user", "content": "Summarize RAG in one line."}],
    }

    first = client.post("/v1/messages", json=payload, headers=headers).json()
    assert first["usage"]["cache_read_input_tokens"] == 0
    assert first["usage"]["cache_creation_input_tokens"] > 0

    second = client.post("/v1/messages", json=payload, headers=headers).json()
    assert second["usage"]["cache_read_input_tokens"] > 0  # cache hit
    assert second["usage"]["cache_creation_input_tokens"] == 0


def test_explicit_block_breakpoint() -> None:
    headers = {"x-api-key": "sk-demo"}
    payload = {
        "model": "claude-haiku-mini",
        "max_tokens": 64,
        "system": [
            {
                "type": "text",
                "text": "You are a careful assistant." * 30,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "workspace": "explicit",
        "messages": [{"role": "user", "content": "What is RAG?"}],
    }

    first = client.post("/v1/messages", json=payload, headers=headers).json()
    assert first["usage"]["cache_creation_input_tokens"] > 0

    second = client.post("/v1/messages", json=payload, headers=headers).json()
    assert second["usage"]["cache_read_input_tokens"] > 0
    # the user message sits after the cached system breakpoint -> uncached input
    assert second["usage"]["input_tokens"] > 0


def test_workspace_isolation_in_server() -> None:
    headers = {"x-api-key": "sk-demo"}
    payload = {
        "model": "claude-haiku-mini",
        "max_tokens": 64,
        "system": [{"type": "text", "text": "x" * 400, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": "hi"}],
    }

    p1 = dict(payload, workspace="tenant-a")
    p2 = dict(payload, workspace="tenant-b")
    client.post("/v1/messages", json=p1, headers=headers)
    second = client.post("/v1/messages", json=p2, headers=headers).json()
    assert second["usage"]["cache_read_input_tokens"] == 0  # isolated


def test_cache_stats_endpoint() -> None:
    # populate the cache a little using a fresh workspace
    headers = {"x-api-key": "sk-demo"}
    payload = {
        "model": "claude-haiku-mini",
        "max_tokens": 32,
        "cache_control": {"type": "ephemeral"},
        "system": "y" * 400,
        "workspace": "stats",
        "messages": [{"role": "user", "content": "hi"}],
    }
    client.post("/v1/messages", json=payload, headers=headers)
    r = client.get("/v1/cache/stats")
    assert r.status_code == 200
    assert r.json()["entries"] >= 1
