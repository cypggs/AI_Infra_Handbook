"""Tests for the tool_call parser."""

import json

import pytest

from tool_use_mini.parser import ParseError, ToolCall, parse_tool_calls


def test_parse_openai_style():
    """Parse the OpenAI-style nested function block."""
    raw = [
        {
            "id": "call_1",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "北京"}',
            },
        }
    ]
    calls, errors = parse_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0] == ToolCall(
        id="call_1", name="get_weather", arguments={"city": "北京"}, raw=raw[0]
    )
    assert errors == []


def test_parse_simplified_style():
    """Parse the simplified flat style."""
    raw = [{"id": "call_2", "name": "calculate_rmb", "arguments": {"amount_usd": 100, "rate": 7}}]
    calls, errors = parse_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0].name == "calculate_rmb"
    assert calls[0].arguments == {"amount_usd": 100, "rate": 7}


def test_parse_missing_name():
    """Entries without a name are reported as parse errors."""
    raw = [{"id": "call_3", "arguments": {}}]
    calls, errors = parse_tool_calls(raw)
    assert calls == []
    assert len(errors) == 1
    assert errors[0].index == 0
    assert "name" in errors[0].reason


def test_parse_invalid_arguments_json():
    """Invalid JSON in arguments string is reported as a parse error."""
    raw = [
        {
            "id": "call_4",
            "function": {
                "name": "get_weather",
                "arguments": "not json",
            },
        }
    ]
    calls, errors = parse_tool_calls(raw)
    assert calls == []
    assert len(errors) == 1
    assert "JSON" in errors[0].reason


def test_parse_non_object_arguments():
    """Arguments that parse to a non-object are rejected."""
    raw = [{"id": "call_5", "name": "get_weather", "arguments": "[1, 2, 3]"}]
    calls, errors = parse_tool_calls(raw)
    assert calls == []
    assert "object" in errors[0].reason


def test_parse_not_a_list():
    """Passing a non-list produces a single parse error."""
    calls, errors = parse_tool_calls({"name": "get_weather"})
    assert calls == []
    assert len(errors) == 1
    assert "list" in errors[0].reason


def test_parse_none():
    """None input returns empty results."""
    calls, errors = parse_tool_calls(None)
    assert calls == []
    assert errors == []


def test_parse_mixed_batch():
    """A batch with one valid and one invalid entry returns both."""
    raw = [
        {"id": "call_ok", "name": "get_weather", "arguments": {"city": "北京"}},
        {"id": "call_bad", "arguments": {}},
    ]
    calls, errors = parse_tool_calls(raw)
    assert len(calls) == 1
    assert len(errors) == 1
    assert errors[0].index == 1
