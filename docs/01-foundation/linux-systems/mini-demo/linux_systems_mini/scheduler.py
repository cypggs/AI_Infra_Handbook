"""CFS scheduler simulator."""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import List


# CFS weight table for nice values -20..19, scaled around nice 0.
def nice_to_weight(nice: int) -> float:
    """Map nice value to CFS-like weight."""
    if not -20 <= nice <= 19:
        raise ValueError("nice must be in [-20, 19]")
    # Approximate exponential mapping: weight = 1024 * 1.25^(-nice)
    return 1024.0 * (1.25 ** (-nice))


@dataclass
class Process:
    """A runnable task in the CFS simulator."""
    pid: int
    name: str
    nice: int = 0
    vruntime: float = 0.0
    runtime: float = 0.0

    @property
    def weight(self) -> float:
        return nice_to_weight(self.nice)

    def __lt__(self, other: "Process") -> bool:
        return self.vruntime < other.vruntime


@dataclass
class CFSScheduler:
    """Minimal CFS scheduler using a priority queue keyed by vruntime."""
    tasks: List[Process] = field(default_factory=list)
    time_slice: float = 10.0  # virtual time units per scheduling decision
    _heap: List[Process] = field(default_factory=list, repr=False)

    def __post_init__(self):
        for t in self.tasks:
            heapq.heappush(self._heap, t)

    def add(self, task: Process) -> None:
        heapq.heappush(self._heap, task)

    def step(self) -> Process | None:
        """Pick the task with smallest vruntime, run it for a slice."""
        if not self._heap:
            return None
        task = heapq.heappop(self._heap)
        # vruntime grows inversely proportional to weight
        delta_v = self.time_slice * (1024.0 / task.weight)
        task.vruntime += delta_v
        task.runtime += self.time_slice
        heapq.heappush(self._heap, task)
        return task

    def run(self, steps: int) -> List[tuple[int, float]]:
        """Run ``steps`` scheduling decisions and return (pid, vruntime) log."""
        log: List[tuple[int, float]] = []
        for _ in range(steps):
            task = self.step()
            if task is None:
                break
            log.append((task.pid, task.vruntime))
        return log

    def normalized_vruntime_spread(self) -> float:
        """Return max(vruntime) - min(vruntime)."""
        if not self._heap:
            return 0.0
        vruntimes = [t.vruntime for t in self._heap]
        return max(vruntimes) - min(vruntimes)
