"""Message types used by agents to communicate."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(Enum):
    """Kinds of messages the bus can carry."""

    DIRECT = "direct"
    BROADCAST = "broadcast"
    EVENT = "event"


@dataclass
class Message:
    """A single message exchanged between agents.

    Use ``recipient="*"`` to broadcast a message to every subscriber of
    ``topic``.
    """

    sender: str
    recipient: str
    topic: str
    content: Any
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    msg_type: MessageType = MessageType.DIRECT

    def __post_init__(self) -> None:
        if self.recipient == "*":
            self.msg_type = MessageType.BROADCAST
