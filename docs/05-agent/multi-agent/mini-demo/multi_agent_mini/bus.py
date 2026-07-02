"""In-memory message bus with publish/subscribe delivery."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Callable

from multi_agent_mini.message import Message, MessageType

Handler = Callable[[Message], None]


class MessageBus:
    """Store and forward messages between agents.

    Subscribers register handlers per topic. Messages are queued until
    ``deliver_all`` flushes them.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Handler]] = defaultdict(list)
        self._pending: deque[Message] = deque()
        self._history: list[Message] = []

    def subscribe(self, topic: str, handler: Handler) -> None:
        """Register ``handler`` to receive messages for ``topic``."""
        self._subscriptions[topic].append(handler)

    def send(self, message: Message) -> None:
        """Queue a message for delivery."""
        self._pending.append(message)

    def broadcast(
        self,
        topic: str,
        content: Any,
        sender: str,
    ) -> Message:
        """Create and queue a broadcast message for ``topic``."""
        message = Message(
            sender=sender,
            recipient="*",
            topic=topic,
            content=content,
            msg_type=MessageType.BROADCAST,
        )
        self.send(message)
        return message

    def deliver_all(self) -> int:
        """Deliver all pending messages to their subscribers.

        Returns the number of messages delivered.
        """
        delivered = 0
        while self._pending:
            message = self._pending.popleft()
            self._history.append(message)
            handlers: list[Handler] = []
            if message.recipient == "*" or message.msg_type == MessageType.BROADCAST:
                handlers = list(self._subscriptions.get(message.topic, []))
            for handler in handlers:
                handler(message)
                delivered += 1
        return delivered

    def pending_count(self) -> int:
        """Return the number of messages waiting to be delivered."""
        return len(self._pending)

    def history(self) -> list[Message]:
        """Return all messages that have been delivered."""
        return list(self._history)
