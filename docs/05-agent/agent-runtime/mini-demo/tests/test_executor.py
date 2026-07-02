"""Tests for the tool executor."""

import time

import pytest

from agent_runtime_mini.executor import ToolExecutionError, ToolExecutor
from agent_runtime_mini.tool_registry import Tool, ToolRegistry, tool


@tool
def echo(value: str, _context=None) -> str:
    """Return the input value."""
    return value


@tool
def fail() -> str:
    """Always raises."""
    raise RuntimeError("boom")


@tool
def slow() -> str:
    """Sleeps longer than the test timeout."""
    time.sleep(0.2)
    return "done"


def _registry_with(*fns):
    registry = ToolRegistry()
    for fn in fns:
        registry.register(
            Tool(
                name=fn._tool_name,
                description=fn._tool_description,
                fn=fn,
                parameters=fn._tool_parameters,
            )
        )
    return registry


def test_execute_success():
    executor = ToolExecutor(_registry_with(echo), timeout=1.0)
    result = executor.execute(
        {"function": {"name": "echo", "arguments": '{"value": "hi"}'}}
    )
    assert result == "hi"


def test_execute_wraps_exception():
    executor = ToolExecutor(_registry_with(fail), timeout=1.0)
    with pytest.raises(ToolExecutionError) as exc_info:
        executor.execute({"function": {"name": "fail", "arguments": "{}"}})
    assert "boom" in str(exc_info.value)


def test_execute_timeout():
    executor = ToolExecutor(_registry_with(slow), timeout=0.05)
    with pytest.raises(ToolExecutionError) as exc_info:
        executor.execute({"function": {"name": "slow", "arguments": "{}"}})
    assert "timed out" in str(exc_info.value).lower()
