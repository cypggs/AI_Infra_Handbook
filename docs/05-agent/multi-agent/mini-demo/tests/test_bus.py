"""Tests for the MessageBus."""

from multi_agent_mini.bus import MessageBus
from multi_agent_mini.message import Message, MessageType


def test_subscribe_and_deliver():
    bus = MessageBus()
    received = []
    bus.subscribe("topic.a", lambda msg: received.append(msg))

    bus.send(Message(sender="x", recipient="*", topic="topic.a", content="hello"))
    assert bus.pending_count() == 1

    delivered = bus.deliver_all()
    assert delivered == 1
    assert bus.pending_count() == 0
    assert len(received) == 1
    assert received[0].content == "hello"


def test_broadcast():
    bus = MessageBus()
    received = []
    bus.subscribe("topic.b", lambda msg: received.append(msg))

    msg = bus.broadcast("topic.b", "broadcast content", sender="coordinator")
    assert msg.msg_type == MessageType.BROADCAST
    bus.deliver_all()
    assert len(received) == 1
    assert received[0].content == "broadcast content"


def test_unsubscribed_topic_is_not_delivered():
    bus = MessageBus()
    received = []
    bus.subscribe("topic.a", lambda msg: received.append(msg))
    bus.send(Message(sender="x", recipient="*", topic="topic.other", content="oops"))
    bus.deliver_all()
    assert received == []


def test_history_tracks_delivered_messages():
    bus = MessageBus()
    bus.send(Message(sender="x", recipient="*", topic="t", content="1"))
    bus.deliver_all()
    assert len(bus.history()) == 1
    assert bus.history()[0].content == "1"
