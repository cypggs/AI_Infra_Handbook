"""Trace observability for the agent runtime."""

import time
from typing import Any


class TraceObserver:
    """Records structured events and renders a simple trace tree."""

    def __init__(self):
        self.events: list[dict[str, Any]] = []
        self._span_counter = 0

    def record(self, event_type: str, **data: Any) -> dict[str, Any]:
        self._span_counter += 1
        event = {
            "span_id": self._span_counter,
            "timestamp": time.time(),
            "type": event_type,
            "data": data,
        }
        self.events.append(event)
        return event

    def render(self) -> str:
        lines = ["Trace:"]
        for event in self.events:
            ts = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
            data = event["data"]
            summary = self._summarize(event["type"], data)
            lines.append(f"  [{ts}] {summary}")
        return "\n".join(lines)

    def _summarize(self, event_type: str, data: dict[str, Any]) -> str:
        if event_type == "task_received":
            return f"task_received session={data.get('session_id')} task={data.get('task')!r}"
        if event_type == "llm_called":
            return f"llm_called iteration={data.get('iteration')}"
        if event_type == "tool_executed":
            return (
                f"tool_executed name={data.get('tool_name')} "
                f"result={data.get('result')!r}"
            )
        if event_type == "guardrail_triggered":
            return f"guardrail_triggered reason={data.get('reason')!r}"
        if event_type == "task_completed":
            return f"task_completed state={data.get('state')} answer={data.get('answer')!r}"
        if event_type == "planning":
            return f"planning subgoals={data.get('subgoals')}"
        return f"{event_type} {data}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"TraceObserver(events={len(self.events)})"
