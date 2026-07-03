"""Event trace / observer for the mini Agent OS.

The Observer records lifecycle and policy events so the demo can print a
schedule trace after execution. It is intentionally simple (no concurrency)
because the whole demo is single-threaded and deterministic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """A single traceable event."""

    kind: str
    source: str
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Observer:
    """Collects events from the kernel, scheduler, sandbox, and agents."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def log(self, kind: str, source: str, **detail: Any) -> None:
        """Append an event to the trace."""
        self.events.append(Event(kind=kind, source=source, detail=detail))

    def filter(self, kind: str) -> list[Event]:
        """Return all events of a given kind."""
        return [e for e in self.events if e.kind == kind]

    def clear(self) -> None:
        """Reset the event trace."""
        self.events.clear()

    def __repr__(self) -> str:
        return f"Observer(events={len(self.events)})"
