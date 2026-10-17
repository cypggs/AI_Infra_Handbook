"""Tests for the mock MCP server."""

import pytest

from mcp_mini.protocol import JSONRPCRequest, METHOD_NOT_FOUND
from mcp_mini.server import MockMCPServer


def _req(method: str, params: dict | None = None, id_: int = 1) -> JSONRPCRequest:
    return JSONRPCRequest(id=id_, method=method, params=params)


def test_initialize():
    server = MockMCPServer()
    response = server.handle(_req("initialize", {"protocolVersion": "2024-11-05"}))
    assert response.result["protocolVersion"] == "2024-11-05"
    assert response.result["serverInfo"]["name"] == "mcp-mini-server"
    assert "tools" in response.result["capabilities"]


def test_tools_list():
    server = MockMCPServer()
    response = server.handle(_req("tools/list"))
    names = [t["name"] for t in response.result["tools"]]
    assert names == ["read_file", "list_directory", "calculator", "get_weather"]


def test_tools_call_read_file():
    server = MockMCPServer()
    response = server.handle(
        _req("tools/call", {"name": "read_file", "arguments": {"path": "/tmp/report.txt"}})
    )
    text = response.result["content"][0]["text"]
    assert "Q2 revenue up 12%" in text


def test_tools_call_calculator():
    server = MockMCPServer()
    response = server.handle(
        _req("tools/call", {"name": "calculator", "arguments": {"expression": "55 * 2"}})
    )
    assert response.result["content"][0]["text"] == "110"


def test_tools_call_get_weather():
    server = MockMCPServer()
    response = server.handle(
        _req("tools/call", {"name": "get_weather", "arguments": {"city": "Austin"}})
    )
    text = response.result["content"][0]["text"]
    assert "sunny" in text
    assert "Austin" in text


def test_resources_read():
    server = MockMCPServer()
    response = server.handle(_req("resources/read", {"uri": "file:///tmp/report.txt"}))
    assert response.result["contents"][0]["text"] == "Q2 revenue up 12%."


def test_prompts_get():
    server = MockMCPServer()
    response = server.handle(_req("prompts/get", {"name": "summary", "arguments": {"topic": "Q2"}}))
    text = response.result["messages"][0]["content"]["text"]
    assert text == "Please summarize: Q2"


def test_unknown_method():
    server = MockMCPServer()
    response = server.handle(_req("foo/bar"))
    assert response.code == METHOD_NOT_FOUND
    assert "foo/bar" in response.message


def test_tools_call_missing_tool_name_returns_invalid_params():
    """协议级参数错误应映射为 JSON-RPC -32602，而不是业务 isError。"""
    from mcp_mini.protocol import INVALID_PARAMS

    server = MockMCPServer()
    response = server.handle(_req("tools/call", {"arguments": {}}))
    assert response.code == INVALID_PARAMS


def test_tools_call_unknown_tool_returns_method_not_found():
    """工具不存在属于协议级错误（-32601），区别于工具内部失败走的 isError=true。"""
    server = MockMCPServer()
    response = server.handle(
        _req("tools/call", {"name": "does_not_exist", "arguments": {}})
    )
    assert response.code == METHOD_NOT_FOUND
    assert "does_not_exist" in response.message


def test_notification_returns_none_sentinel():
    server = MockMCPServer()
    response = server.handle(JSONRPCRequest(id=None, method="notifications/initialized"))
    assert response.id is None
    assert response.result is None
