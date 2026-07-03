"""Tests for the deterministic mock LLM client."""

import pytest

from tool_use_mini.llm_client import MockLLMClient


def test_client_turn_sequence():
    """The client must emit the scripted four-turn sequence."""
    client = MockLLMClient()

    r0 = client.chat([{"role": "user", "content": "hello"}])
    assert r0.finish_reason == "tool_calls"
    assert len(r0.tool_calls) == 2
    assert r0.tool_calls[0]["function"]["name"] == "get_weather"
    assert r0.tool_calls[1]["function"]["name"] == "get_exchange_rate"

    r1 = client.chat([])
    assert r1.finish_reason == "tool_calls"
    assert len(r1.tool_calls) == 1
    assert r1.tool_calls[0]["function"]["name"] == "calculate_rmb"
    # Malformed: rate is a string
    args = r1.tool_calls[0]["function"]["arguments"]
    assert '"rate": "7.25"' in args

    r2 = client.chat([])
    assert r2.finish_reason == "tool_calls"
    assert len(r2.tool_calls) == 1
    assert '"rate": 7.25' in r2.tool_calls[0]["function"]["arguments"]

    r3 = client.chat([])
    assert r3.finish_reason == "stop"
    assert "7250" in r3.content


def test_client_records_messages():
    """The client records the assistant responses it generates."""
    client = MockLLMClient()
    client.chat([{"role": "user", "content": "q"}])
    assert len(client.messages) == 1  # assistant response only
    assert client.messages[0]["role"] == "assistant"
    client.chat([])
    assert len(client.messages) == 2  # another assistant response


def test_client_reset():
    """Reset should clear state."""
    client = MockLLMClient()
    client.chat([{"role": "user", "content": "q"}])
    client.chat([])
    client.reset()
    assert client.turn == 0
    assert client.messages == []
