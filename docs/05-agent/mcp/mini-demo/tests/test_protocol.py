"""Tests for JSON-RPC message serialization."""

import pytest

from mcp_mini.protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCErrorResponse,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    make_error,
    make_request,
    make_response,
    parse_message,
)


def test_request_serialization_roundtrip():
    req = make_request(1, "initialize", {"protocolVersion": "2024-11-05"})
    raw = req.serialize()
    parsed = parse_message(raw)
    assert isinstance(parsed, JSONRPCRequest)
    assert parsed.id == 1
    assert parsed.method == "initialize"
    assert parsed.params["protocolVersion"] == "2024-11-05"


def test_response_serialization_roundtrip():
    resp = make_response(1, {"tools": []})
    raw = resp.serialize()
    parsed = parse_message(raw)
    assert isinstance(parsed, JSONRPCResponse)
    assert parsed.id == 1
    assert parsed.result == {"tools": []}


def test_error_serialization_roundtrip():
    err = make_error(42, METHOD_NOT_FOUND, "Method not found")
    raw = err.serialize()
    parsed = parse_message(raw)
    assert isinstance(parsed, JSONRPCErrorResponse)
    assert parsed.id == 42
    assert parsed.code == METHOD_NOT_FOUND
    assert parsed.message == "Method not found"


def test_parse_invalid_json():
    with pytest.raises(JSONRPCError) as exc_info:
        parse_message("not json")
    assert exc_info.value.code == PARSE_ERROR


def test_parse_non_object():
    with pytest.raises(JSONRPCError) as exc_info:
        parse_message('["list"]')
    assert exc_info.value.code == -32600


def test_notification_has_no_id():
    req = JSONRPCRequest(id=None, method="notifications/initialized")
    assert req.serialize() == '{"jsonrpc":"2.0","id":null,"method":"notifications/initialized"}'
