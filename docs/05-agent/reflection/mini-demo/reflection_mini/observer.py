"""Observer for recording and rendering reflection loop events."""

from datetime import datetime
from typing import Any


class Observer:
    """Records structured events and renders them as an execution trace."""

    def __init__(self) -> None:
        """Create an empty observer."""
        self.events: list[dict[str, Any]] = []

    def record(self, event_type: str, **data: Any) -> None:
        """Append an event to the trace.

        Args:
            event_type: Category for the event, e.g. ``generate`` or
                ``finalize``.
            **data: Additional key/value pairs describing the event.
        """
        self.events.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "event_type": event_type,
                **data,
            }
        )

    def render(self) -> str:
        """Render the recorded events as a human-readable tree.

        Returns:
            A multi-line string with one line per event.
        """
        lines = ["Reflection trace:"]
        for idx, event in enumerate(self.events, start=1):
            ts = event.get("timestamp", "")
            event_type = event.get("event_type", "unknown")
            payload = {k: v for k, v in event.items() if k not in ("timestamp", "event_type")}
            details = ", ".join(f"{k}={v!r}" for k, v in payload.items())
            branch = "└──" if idx == len(self.events) else "├──"
            lines.append(f"{branch} [{ts}] {event_type}" + (f" | {details}" if details else ""))
        return "\n".join(lines)

    def print_trace(self) -> None:
        """Print the rendered trace to stdout."""
        print(self.render())
