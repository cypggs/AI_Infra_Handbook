"""Observer records a trace of planning, execution, and replanning events."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class Observer:
    """Simple event collector used to inspect a planning run.

    Attributes:
        events: Chronological list of event records. Each record is a dict with
            keys ``event_type``, ``step_id`` (optional), and ``message``.
    """

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def record(
        self,
        event_type: str,
        step_id: Optional[str] = None,
        message: str = "",
    ) -> None:
        """Append a new event to the trace."""
        self.events.append(
            {
                "event_type": event_type,
                "step_id": step_id,
                "message": message,
            }
        )

    def __repr__(self) -> str:
        return f"Observer(events={self.events!r})"
