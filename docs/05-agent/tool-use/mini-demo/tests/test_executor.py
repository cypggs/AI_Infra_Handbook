"""Tests for the tool call executor."""

import time

import pytest

from tool_use_mini.executor import Executor, ToolResult
from tool_use_mini.parser import ToolCall
from tool_use_mini.tool import Tool, ToolRegistry, build_default_registry


def test_execute_single_call():
    """Executor runs a single tool call."""
    registry = build_default_registry()
    executor = Executor(registry)
    call = ToolCall(id="c1", name="get_weather", arguments={"city": "北京"})
    results = executor.execute([call])
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].data["city"] == "北京"


def test_execute_parallel():
    """Executor runs multiple calls in parallel."""
    registry = build_default_registry()
    executor = Executor(registry)
    calls = [
        ToolCall(id="c1", name="get_weather", arguments={"city": "北京"}),
        ToolCall(id="c2", name="get_weather", arguments={"city": "上海"}),
    ]
    results = executor.execute(calls)
    assert len(results) == 2
    assert {r.name for r in results} == {"get_weather"}
    assert all(r.success for r in results)


def test_execute_unknown_tool():
    """Executing an unknown tool returns a failure result."""
    registry = ToolRegistry()
    executor = Executor(registry)
    call = ToolCall(id="c1", name="missing", arguments={})
    result = executor.execute_one(call)
    assert result.success is False
    assert "not found" in result.error


def test_execute_retry_then_success():
    """A flaky tool that raises once should succeed on retry."""
    attempts = {"count": 0}

    def flaky(x):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient")
        return {"x": x}

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="flaky",
            description="",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
            },
            func=flaky,
        )
    )
    executor = Executor(registry, default_max_retries=2)
    call = ToolCall(id="c1", name="flaky", arguments={"x": 1})
    result = executor.execute_one(call)
    assert result.success is True
    assert result.data == {"x": 1}
    assert result.attempts == 2


def test_execute_fallback():
    """A failing tool with fallback uses the fallback value."""
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="fail",
            description="",
            parameters={"type": "object"},
            func=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    )
    executor = Executor(registry, default_max_retries=1, default_fallback={"error": "fallback"})
    call = ToolCall(id="c1", name="fail", arguments={})
    result = executor.execute_one(call)
    assert result.success is True
    assert result.data == {"error": "fallback"}
    assert result.error is not None
    assert "fallback" in result.error


def test_execute_timeout():
    """A slow tool exceeds its per-call timeout."""

    def slow():
        time.sleep(2)
        return "done"

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="slow",
            description="",
            parameters={"type": "object"},
            func=slow,
        )
    )
    executor = Executor(registry, default_timeout=0.1)
    call = ToolCall(id="c1", name="slow", arguments={})
    result = executor.execute_one(call)
    assert result.success is False
    assert "timeout" in result.error.lower()


def test_execute_preserves_call_order():
    """Results are returned in the same order as the input calls."""
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "number"}},
                "required": ["value"],
            },
            func=lambda value: value,
        )
    )
    executor = Executor(registry)
    calls = [ToolCall(id=f"c{i}", name="echo", arguments={"value": i}) for i in range(5)]
    results = executor.execute(calls)
    assert [r.data for r in results] == [0, 1, 2, 3, 4]
