"""Tests for client session request/response matching and timeout."""

import pytest

from mcp_mini.protocol import (
    JSONRPCError,
    METHOD_NOT_FOUND,
    make_error,
    make_request,
    make_response,
)
from mcp_mini.session import ClientSession
from mcp_mini.transport import InMemoryTransport


def test_request_id_increments_sequentially():
    transport = InMemoryTransport()
    session = ClientSession(transport=transport)

    # Pre-stage responses so the blocking requests complete immediately.
    transport.feed(make_response(1, {}))
    transport.feed(make_response(2, {}))
    transport.feed(make_response(3, {}))

    session.request("tools/list")
    session.request("tools/list")
    session.request("tools/list")

    ids = [int(raw.split('"id":')[1].split(",")[0]) for raw in transport.outgoing]
    assert ids == [1, 2, 3]


def test_request_response_matching():
    transport = InMemoryTransport()
    session = ClientSession(transport=transport)

    # Pre-stage a response with mismatched id, then the correct one.
    transport.feed(make_response(99, {"tools": []}))
    transport.feed(make_response(1, {"tools": [{"name": "x"}]}))

    result = session.request("tools/list")
    assert result["tools"][0]["name"] == "x"


def test_request_timeout():
    transport = InMemoryTransport()
    session = ClientSession(transport=transport, timeout=0.05)

    with pytest.raises(TimeoutError):
        session.request("tools/list")


def test_error_response_raises_jsonrpc_error():
    transport = InMemoryTransport()
    session = ClientSession(transport=transport)

    transport.feed(make_error(1, METHOD_NOT_FOUND, "nope"))

    with pytest.raises(JSONRPCError) as exc_info:
        session.request("tools/list")
    assert exc_info.value.code == METHOD_NOT_FOUND
