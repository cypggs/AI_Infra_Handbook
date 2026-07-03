"""Tests for Tool, ToolRegistry, and built-in tools."""

import pytest

from tool_use_mini.tool import (
    Tool,
    ToolRegistry,
    build_default_registry,
    reset_exchange_rate_service,
)


def test_register_and_get():
    """Tools can be registered and looked up by name."""
    registry = ToolRegistry()
    tool = Tool(
        name="add",
        description="Add two numbers.",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        func=lambda a, b: a + b,
    )
    registry.register(tool)
    assert registry.get("add") is tool
    assert len(registry.list_tools()) == 1


def test_get_missing_raises():
    """Looking up an unknown tool raises KeyError."""
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.get("missing")


def test_call_tool():
    """Registry.call should invoke the tool function."""
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="concat",
            description="Concatenate strings.",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}, "y": {"type": "string"}},
                "required": ["x", "y"],
            },
            func=lambda x, y: x + y,
        )
    )
    assert registry.call("concat", {"x": "a", "y": "b"}) == "ab"


def test_default_registry_tools():
    """The default registry contains the three demo tools."""
    registry = build_default_registry()
    names = {t.name for t in registry.list_tools()}
    assert names == {"get_weather", "get_exchange_rate", "calculate_rmb"}


def test_get_weather_beijing():
    """Weather returns deterministic Beijing data."""
    registry = build_default_registry()
    result = registry.call("get_weather", {"city": "北京"})
    assert result["city"] == "北京"
    assert result["condition"] == "晴"


def test_exchange_rate_failure_then_success():
    """Exchange rate returns an error on first call, then a cached rate."""
    reset_exchange_rate_service()
    registry = build_default_registry()

    first = registry.call("get_exchange_rate", {"from_currency": "USD", "to_currency": "CNY"})
    assert first["success"] is False
    assert "fallback_rate" in first

    second = registry.call("get_exchange_rate", {"from_currency": "USD", "to_currency": "CNY"})
    assert second["success"] is True
    assert second["rate"] == first["fallback_rate"]


def test_calculate_rmb():
    """RMB calculation is correct."""
    registry = build_default_registry()
    result = registry.call("calculate_rmb", {"amount_usd": 1000, "rate": 7.25})
    assert result["amount_rmb"] == 7250.0


def test_tool_definition_shape():
    """Tool.to_dict follows the OpenAI function shape."""
    tool = Tool(
        name="x",
        description="d",
        parameters={"type": "object"},
        func=lambda: None,
    )
    definition = tool.to_dict()
    assert definition["type"] == "function"
    assert definition["function"]["name"] == "x"
    assert definition["function"]["parameters"] == {"type": "object"}
