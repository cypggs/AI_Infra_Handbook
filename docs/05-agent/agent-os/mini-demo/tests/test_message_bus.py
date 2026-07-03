"""Tests for the simple message bus."""

from agent_os_mini.message_bus import MessageBus


def test_message_bus_send_and_deliver():
    bus = MessageBus()
    bus.register("p1")
    bus.register("p2")

    msg = bus.send("p1", "p2", "result", 42)

    assert msg.sender == "p1"
    assert msg.recipient == "p2"
    assert msg.topic == "result"
    assert msg.payload == 42
    assert bus.inbox("p2") == [msg]
    assert bus.outbox("p1") == [msg]


def test_message_bus_on_deliver_callback():
    delivered = []
    bus = MessageBus(on_deliver=lambda pid: delivered.append(pid))
    bus.send("p1", "p2", "ping", None)

    assert delivered == ["p2"]


def test_message_bus_unregister():
    bus = MessageBus()
    bus.register("p1")
    bus.unregister("p1")

    assert bus.inbox("p1") == []
    assert bus.outbox("p1") == []


def test_message_bus_clear_inbox():
    bus = MessageBus()
    bus.send("p1", "p2", "x", 1)
    bus.clear_inbox("p2")

    assert bus.inbox("p2") == []
    assert bus.outbox("p1")  # outbox is not cleared
