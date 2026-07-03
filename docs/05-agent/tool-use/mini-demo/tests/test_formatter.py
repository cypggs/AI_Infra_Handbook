"""Tests for result formatting."""

import json

from tool_use_mini.executor import ToolResult
from tool_use_mini.formatter import format_results, format_tool_message, format_assistant_message


def test_format_success_result():
    """Successful results are serialized to JSON."""
    result = ToolResult(
        call_id="c1",
        name="get_weather",
        arguments={"city": "北京"},
        success=True,
        data={"city": "北京", "temperature_c": 28},
    )
    messages = format_results([result])
    assert len(messages) == 1
    assert messages[0].role == "tool"
    assert messages[0].tool_call_id == "c1"
    assert messages[0].name == "get_weather"
    assert "北京" in messages[0].content
    assert "28" in messages[0].content


def test_format_error_result():
    """Failed results carry an error payload."""
    result = ToolResult(
        call_id="c2",
        name="missing",
        arguments={},
        success=False,
        error="Tool not found",
    )
    messages = format_results([result])
    assert len(messages) == 1
    payload = json.loads(messages[0].content)
    assert payload["error"] == "Tool not found"


def test_format_tool_message_dict():
    """format_tool_message returns a plain dict."""
    result = ToolResult(
        call_id="c3",
        name="calculate_rmb",
        arguments={"amount_usd": 1000, "rate": 7.25},
        success=True,
        data={"amount_rmb": 7250.0},
    )
    message = format_tool_message(result)
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "c3"
    assert message["name"] == "calculate_rmb"
    assert json.loads(message["content"])["amount_rmb"] == 7250.0


def test_format_assistant_message():
    """format_assistant_message builds an assistant message with tool_calls."""
    tool_calls = [{"id": "c1", "function": {"name": "get_weather", "arguments": "{}"}}]
    message = format_assistant_message("", tool_calls)
    assert message["role"] == "assistant"
    assert message["content"] == ""
    assert message["tool_calls"] is tool_calls
