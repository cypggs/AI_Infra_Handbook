"""In-memory trace / span recorder for the benchmark mini-demo."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterator, List, Optional


@dataclass
class Span:
    name: str
    start: int
    end: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[tuple[str, Dict[str, Any], int]] = field(default_factory=list)
    children: List["Span"] = field(default_factory=list)
    parent: Optional["Span"] = None

    @property
    def duration(self) -> int:
        return (self.end if self.end is not None else self.start) - self.start

    def walk(self) -> Iterator["Span"]:
        yield self
        for child in self.children:
            yield from child.walk()


class Tracer:
    """Simple hierarchical tracer with deterministic clock."""

    def __init__(self) -> None:
        self._clock = 0
        self.root = Span("root", self._clock)
        self._current = self.root

    def advance(self, ticks: int) -> int:
        self._clock += ticks
        return self._clock

    @property
    def now(self) -> int:
        return self._clock

    @property
    def total_latency(self) -> int:
        return self._clock

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Generator[Span, None, None]:
        child = Span(name, self._clock, attributes=dict(attrs), parent=self._current)
        self._current.children.append(child)
        self._current = child
        try:
            yield child
        finally:
            child.end = self._clock
            self._current = child.parent

    def add_event(self, name: str, **attrs: Any) -> None:
        self._current.events.append((name, dict(attrs), self._clock))

    def total_tokens(self) -> int:
        return sum(span.attributes.get("tokens", 0) for span in self.root.walk())

    def tool_calls(self) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        for span in self.root.walk():
            if span.name == "tool.call":
                calls.append({
                    "tool": span.attributes.get("tool"),
                    "input": span.attributes.get("input"),
                    "output": span.attributes.get("output"),
                    "error": span.attributes.get("error"),
                })
        return calls

    def has_error_event(self) -> bool:
        for span in self.root.walk():
            for event_name, _, _ in span.events:
                if event_name == "tool.error":
                    return True
        return False
