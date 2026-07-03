import json

import pytest
from fastapi.testclient import TestClient

from openai_mini.server import app

client = TestClient(app)

HEADERS = {"Authorization": "Bearer sk-demo", "Content-Type": "application/json"}


def test_models_endpoint():
    r = client.get("/v1/models", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "list"
    assert {m["id"] for m in data["data"]} == {"gpt-mini", "gpt-large"}


def test_chat_completion_non_stream():
    payload = {
        "model": "gpt-mini",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    r = client.post("/v1/chat/completions", json=payload, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "gpt-mini"
    assert "Hello! This is gpt-mini" in data["choices"][0]["message"]["content"]
    assert "usage" in data


def test_chat_completion_stream():
    payload = {
        "model": "gpt-large",
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }
    r = client.post("/v1/chat/completions", json=payload, headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    collected = []
    for line in r.text.splitlines():
        if line.startswith("data: "):
            chunk = line[6:]
            if chunk == "[DONE]":
                break
            collected.append(json.loads(chunk))
    assert len(collected) > 0
    text = "".join(
        c["choices"][0]["delta"].get("content", "") for c in collected
    ).strip()
    assert "Greetings from gpt-large" in text


def test_unauthorized():
    r = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-mini", "messages": [{"role": "user", "content": "x"}]},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_invalid_model():
    r = client.post(
        "/v1/chat/completions",
        json={"model": "foo-bar", "messages": [{"role": "user", "content": "x"}]},
        headers=HEADERS,
    )
    assert r.status_code == 400


def test_rate_limit():
    # Drain the bucket quickly; the first BURST should succeed then we hit 429.
    # Bucket capacity is 20, so 21st request should be limited.
    payload = {"model": "gpt-mini", "messages": [{"role": "user", "content": "x"}]}
    status_codes = []
    for _ in range(25):
        r = client.post("/v1/chat/completions", json=payload, headers=HEADERS)
        status_codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in status_codes
