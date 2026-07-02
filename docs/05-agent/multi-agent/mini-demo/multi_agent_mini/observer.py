"""Simple observer that records agent events and renders a trace."""

from __future__ import annotations

import time
from typing import Any


class Observer:
    """Records structured events for later inspection."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._counter = 0

    def record(self, event_type: str, **data: Any) -> dict[str, Any]:
        """Append an event and return it."""
        self._counter += 1
        event = {
            "id": self._counter,
            "timestamp": time.time(),
            "type": event_type,
            "data": data,
        }
        self.events.append(event)
        return event

    def render(self) -> str:
        """Return a human-readable trace of recorded events."""
        lines = ["Observer trace:"]
        for event in self.events:
            ts = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
            summary = self._summarize(event["type"], event["data"])
            lines.append(f"  [{ts}] {summary}")
        return "\n".join(lines)

    def _summarize(self, event_type: str, data: dict[str, Any]) -> str:
        agent = data.get("agent")
        prefix = f"{agent}: " if agent else ""
        if event_type == "llm_decision":
            return f"{prefix}decision={data.get('decision')}"
        if event_type == "skill_executed":
            return f"{prefix}skill={data.get('skill')} result={data.get('result')!r}"
        if event_type == "handoff":
            return f"{prefix}handoff to={data.get('to')}"
        if event_type == "finalize":
            return f"{prefix}finalize"
        return f"{prefix}{event_type} {data}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"Observer(events={len(self.events)})"
