"""Tests for Gateway routing and canary split."""
from __future__ import annotations

from kserve_mini.dataplane import FakeModelServer
from kserve_mini.gateway import Gateway


def test_gateway_v1_request() -> None:
    gw = Gateway(host="iris.default.example.com")
    gw.set_stable(FakeModelServer(name="iris-v1", runtime_name="sklearn"))
    resp = gw.route("v1", {"instances": [[1.0, 2.0, 3.0, 4.0]]})
    assert resp.status_code == 200
    assert resp.body["model"] == "iris-v1"
    assert "predictions" in resp.body


def test_gateway_v2_request() -> None:
    gw = Gateway(host="iris.default.example.com")
    gw.set_stable(FakeModelServer(name="iris-v1", runtime_name="triton"))
    resp = gw.route("v2", {"inputs": [{"name": "input", "shape": [1, 4], "datatype": "FP32", "data": [1.0, 2.0, 3.0, 4.0]}]})
    assert resp.status_code == 200
    assert resp.body["model_name"] == "iris-v1"


def test_gateway_openai_request() -> None:
    gw = Gateway(host="llm.default.example.com")
    gw.set_stable(FakeModelServer(name="llama-3", runtime_name="vllm"))
    resp = gw.route("openai", {"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 200
    assert resp.body["model"] == "llama-3"
    assert resp.body["choices"][0]["message"]["role"] == "assistant"


def test_gateway_canary_split() -> None:
    gw = Gateway(host="iris.default.example.com")
    gw.set_stable(FakeModelServer(name="stable", runtime_name="sklearn"))
    gw.set_canary(FakeModelServer(name="canary", runtime_name="sklearn"), percent=30)

    counts = {"stable": 0, "canary": 0}
    for _ in range(2000):
        resp = gw.route("v1", {"instances": [[1.0]]})
        counts[resp.body["model"]] += 1

    # Allow 5% tolerance for randomness.
    total = sum(counts.values())
    assert counts["canary"] / total >= 0.25
    assert counts["canary"] / total <= 0.35


def test_gateway_no_stable_returns_503() -> None:
    gw = Gateway(host="iris.default.example.com")
    resp = gw.route("v1", {"instances": [[1.0]]})
    assert resp.status_code == 503
