"""I/O scheduler simulator."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, List


@dataclass
class DiskRequest:
    """A single block I/O request."""
    req_id: int
    owner: int  # pid
    lba: int    # logical block address
    deadline: float  # absolute deadline
    size: int = 1


@dataclass
class IOScheduler:
    """Simplified noop / deadline / cfq I/O scheduler."""
    policy: str = "noop"  # noop | deadline | cfq
    requests: List[DiskRequest] = field(default_factory=list)
    _cfq_queue: "defaultdict[int, Deque[DiskRequest]]" = field(
        default_factory=lambda: defaultdict(deque), repr=False
    )

    def __post_init__(self):
        for r in self.requests:
            self._cfq_queue[r.owner].append(r)

    def add(self, req: DiskRequest) -> None:
        self.requests.append(req)
        self._cfq_queue[req.owner].append(req)

    def schedule(self, current_time: float) -> List[DiskRequest]:
        """Return ordered list of requests to dispatch."""
        if self.policy == "noop":
            return list(self.requests)
        if self.policy == "deadline":
            # Deadline: prefer requests whose deadline is closest
            return sorted(self.requests, key=lambda r: r.deadline)
        if self.policy == "cfq":
            # CFQ: round-robin across owners, FIFO within each owner
            ordered: List[DiskRequest] = []
            owners = list(self._cfq_queue.keys())
            while any(self._cfq_queue[o] for o in owners):
                for owner in owners:
                    if self._cfq_queue[owner]:
                        ordered.append(self._cfq_queue[owner].popleft())
            return ordered
        raise ValueError(f"Unknown policy: {self.policy}")

    def service_times(self, current_time: float, per_unit: float = 1.0) -> List[float]:
        """Return per-request completion time under current ordering."""
        time = current_time
        times: List[float] = []
        for req in self.schedule(current_time):
            time += req.size * per_unit
            times.append(time)
        return times

    def deadline_misses(self, current_time: float) -> int:
        """Count how many requests would miss deadline."""
        misses = 0
        for req, completion in zip(self.schedule(current_time), self.service_times(current_time)):
            if completion > req.deadline:
                misses += 1
        return misses
