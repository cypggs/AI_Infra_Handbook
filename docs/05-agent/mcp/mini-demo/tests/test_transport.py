"""Tests for in-memory transport."""

import pytest

from mcp_mini.protocol import JSONRPCError, make_request, make_response
from mcp_mini.transport import InMemoryTransport


def test_send_and_receive_order():
    transport = InMemoryTransport()
    transport.send(make_request(1, "a"))
    transport.send(make_request(2, "b"))
    transport.send(make_response(1, "ok"))

    assert transport.outgoing_count == 3
    assert len(transport.outgoing) == 3

    msg1 = transport.pop_outgoing()
    msg2 = transport.pop_outgoing()
    msg3 = transport.pop_outgoing()

    assert msg1.method == "a"
    assert msg2.method == "b"
    assert msg3.result == "ok"
    assert transport.outgoing_count == 0


def test_feed_and_receive():
    transport = InMemoryTransport()
    transport.feed(make_request(7, "tools/list"))
    msg = transport.receive()
    assert msg.id == 7
    assert msg.method == "tools/list"


def test_receive_empty_raises():
    transport = InMemoryTransport()
    with pytest.raises(JSONRPCError):
        transport.receive()


def test_outgoing_snapshot_is_independent():
    transport = InMemoryTransport()
    transport.send(make_request(1, "x"))
    snapshot = transport.outgoing
    transport.send(make_request(2, "y"))
    assert len(snapshot) == 1
    assert transport.outgoing_count == 2
