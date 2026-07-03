"""Simple inbox/outbox message bus for inter-process communication.

Each process has an inbox and an outbox. The bus delivers messages by copying
them from a sender's outbox into a recipient's inbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Message:
    """A message sent from one process to another."""

    sender: str
    recipient: str
    topic: str
    payload: Any


class MessageBus:
    """In-memory message bus with per-process inboxes and outboxes."""

    def __init__(self, on_deliver: Callable[[str], None] | None = None) -> None:
        self._inboxes: dict[str, list[Message]] = {}
        self._outboxes: dict[str, list[Message]] = {}
        # Optional callback invoked with the recipient pid whenever a message is delivered.
        self._on_deliver = on_deliver

    def register(self, pid: str) -> None:
        """Create inbox and outbox for a process."""
        self._inboxes.setdefault(pid, [])
        self._outboxes.setdefault(pid, [])

    def unregister(self, pid: str) -> None:
        """Remove a process's mailboxes."""
        self._inboxes.pop(pid, None)
        self._outboxes.pop(pid, None)

    def send(self, sender: str, recipient: str, topic: str, payload: Any) -> Message:
        """Deliver a message from sender to recipient."""
        self.register(sender)
        self.register(recipient)
        msg = Message(sender=sender, recipient=recipient, topic=topic, payload=payload)
        self._outboxes[sender].append(msg)
        self._inboxes[recipient].append(msg)
        if self._on_deliver is not None:
            self._on_deliver(recipient)
        return msg

    def inbox(self, pid: str) -> list[Message]:
        """Return the current inbox for a process (newest first)."""
        self.register(pid)
        # Return a copy so callers cannot mutate internal state.
        return list(self._inboxes[pid])

    def outbox(self, pid: str) -> list[Message]:
        """Return the current outbox for a process (newest first)."""
        self.register(pid)
        return list(self._outboxes[pid])

    def clear_inbox(self, pid: str) -> None:
        """Empty a process's inbox."""
        self.register(pid)
        self._inboxes[pid].clear()

    def clear_outbox(self, pid: str) -> None:
        """Empty a process's outbox."""
        self.register(pid)
        self._outboxes[pid].clear()

    def __repr__(self) -> str:
        return f"MessageBus(processes={list(self._inboxes)})"
