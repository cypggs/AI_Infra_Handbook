from llm_gateway_mini.transform import (
    normalize_messages,
    openai_to_provider,
    provider_to_openai,
)


def test_normalize_messages():
    assert normalize_messages([{"role": "user", "content": "hi"}]) == [
        {"role": "user", "content": "hi"}
    ]
    assert normalize_messages(None) == []
    assert normalize_messages([{"content": "no role"}]) == [
        {"role": "user", "content": "no role"}
    ]


def test_openai_to_provider_vllm():
    req = {
        "model": "m",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.5,
    }
    pr = openai_to_provider("vllm", req)
    assert pr["provider_type"] == "vllm"
    assert pr["vllm_specific"]["ignore_eos"] is False
    assert pr["messages"][0]["content"] == "hi"


def test_openai_to_provider_triton():
    req = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    pr = openai_to_provider("triton", req)
    assert pr["provider_type"] == "triton"
    assert pr["triton_specific"]["protocol"] == "http"


def test_openai_to_provider_openai():
    req = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    pr = openai_to_provider("openai", req)
    assert pr["provider_type"] == "openai"
    assert "vllm_specific" not in pr
    assert "triton_specific" not in pr


def test_provider_to_openai_adds_provider():
    raw = {
        "id": "x",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [],
        "usage": {},
    }
    resp = provider_to_openai("p", {"model": "m"}, raw)
    assert resp["provider"] == "p"
    assert resp["model"] == "m"


def test_provider_to_openai_fills_missing_fields():
    resp = provider_to_openai("p", {"model": "m"}, {})
    assert resp["object"] == "chat.completion"
    assert "choices" in resp
    assert "usage" in resp
    assert resp["provider"] == "p"
