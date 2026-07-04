"""Packet dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Packet:
    """A simplified network packet."""
    src_ip: str
    dst_ip: str
    payload: Any = None
    seq: int = 0
    ack: int = 0
    flags: str = ""
    ttl: int = 64
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Packet({self.src_ip} -> {self.dst_ip}, seq={self.seq}, flags={self.flags!r})"
