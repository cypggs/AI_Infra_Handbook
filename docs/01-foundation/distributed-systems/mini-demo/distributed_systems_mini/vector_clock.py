"""Vector clock implementation for detecting concurrency and merging versions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal


@dataclass
class VectorClock:
    """Per-node vector clock.

    The clock is a map from node identifier to event count.  ``compare``
    returns the Happens-Before relationship between two vector clocks, and
    ``merge`` produces the least upper bound of two clocks.
    """

    node_id: str
    vector: Dict[str, int] = field(default_factory=dict)

    def increment(self) -> "VectorClock":
        self.vector[self.node_id] = self.vector.get(self.node_id, 0) + 1
        return self

    def update(self, other: "VectorClock") -> None:
        for k, v in other.vector.items():
            self.vector[k] = max(self.vector.get(k, 0), v)

    def compare(self, other: "VectorClock") -> Literal["before", "after", "concurrent", "equal"]:
        keys = set(self.vector.keys()) | set(other.vector.keys())
        less = greater = False
        for k in keys:
            a = self.vector.get(k, 0)
            b = other.vector.get(k, 0)
            if a < b:
                less = True
            elif a > b:
                greater = True
        if less and greater:
            return "concurrent"
        if less:
            return "before"
        if greater:
            return "after"
        return "equal"

    def merge(self, other: "VectorClock") -> "VectorClock":
        vc = VectorClock(self.node_id)
        vc.update(self)
        vc.update(other)
        return vc

    def __repr__(self) -> str:
        return f"VectorClock({self.node_id!r}, {self.vector})"
