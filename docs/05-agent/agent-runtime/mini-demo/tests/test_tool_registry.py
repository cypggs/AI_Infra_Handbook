"""Tests for the tool registry and built-in tools."""

import pytest

from agent_runtime_mini.tool_registry import (
    ToolRegistry,
    calculator,
    default_tool_registry,
    search,
    write_file,
)


def test_default_schemas():
    registry = default_tool_registry()
    schemas = {s["function"]["name"]: s["function"]["parameters"] for s in registry.schemas()}
    assert set(schemas) == {"calculator", "search", "read_file", "write_file"}
    assert schemas["calculator"]["properties"]["expr"]["type"] == "string"
    assert "expr" in schemas["calculator"]["required"]
    assert schemas["write_file"]["properties"]["path"]["type"] == "string"
    assert "content" in schemas["write_file"]["required"]


def test_calculator():
    assert calculator(expr="25*4+10") == 110.0
    assert calculator(expr="(2+3)*4") == 20.0


def test_calculator_rejects_unsafe_code():
    with pytest.raises(ValueError):
        calculator(expr="__import__('os').system('ls')")


def test_search():
    assert "president" in search(query="current president of the US").lower()
    assert "sunny" in search(query="weather today").lower()


def test_dispatch():
    registry = default_tool_registry()
    result = registry.dispatch(
        {
            "function": {
                "name": "calculator",
                "arguments": '{"expr": "1+2+3"}',
            }
        }
    )
    assert result == 6.0


def test_write_file_requires_approval():
    with pytest.raises(PermissionError):
        write_file(path="/tmp/test.txt", content="hello")


def test_write_file_with_approval():
    result = write_file(
        path="/tmp/approved.txt",
        content="hello",
        _context={"approved": True},
    )
    assert "Wrote" in result
