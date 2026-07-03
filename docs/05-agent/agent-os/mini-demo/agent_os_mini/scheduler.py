"""Schedulers for the mini Agent OS.

Two policies are demonstrated:
- RoundRobinScheduler: cycles through ready processes in insertion order.
- PriorityScheduler: always picks the ready process with the highest priority.
"""

from __future__ import annotations

from typing import Any

from .process import AgentProcess


class RoundRobinScheduler:
    """Simple round-robin scheduler over ready processes."""

    def __init__(self, observer: Any) -> None:
        self.observer = observer
        self._ready: list[AgentProcess] = []
        self._index = 0

    def _log(self, kind: str, **detail: Any) -> None:
        if self.observer is not None:
            self.observer.log(kind, "scheduler", **detail)

    def add(self, process: AgentProcess) -> None:
        """Add a process to the ready queue."""
        if process not in self._ready:
            self._ready.append(process)
            self._log("scheduler_add", pid=process.pid)

    def remove(self, process: AgentProcess) -> None:
        """Remove a process from the ready queue."""
        if process in self._ready:
            idx = self._ready.index(process)
            self._ready.remove(process)
            if self._index >= idx and self._index > 0:
                self._index -= 1
            self._log("scheduler_remove", pid=process.pid)

    def next(self) -> AgentProcess | None:
        """Return the next ready process, or None if none are ready."""
        ready = [p for p in self._ready if p.is_ready()]
        if not ready:
            return None
        if self._index >= len(ready):
            self._index = 0
        process = ready[self._index]
        self._index = (self._index + 1) % len(ready)
        self._log("scheduler_pick", pid=process.pid)
        return process

    def tick(self) -> None:
        """Advance the scheduling pointer (no-op for round-robin)."""
        pass

    def __repr__(self) -> str:
        return f"RoundRobinScheduler(ready={[p.pid for p in self._ready]})"


class PriorityScheduler:
    """Scheduler that picks the ready process with the highest priority."""

    def __init__(self, observer: Any) -> None:
        self.observer = observer
        self._ready: list[AgentProcess] = []

    def _log(self, kind: str, **detail: Any) -> None:
        if self.observer is not None:
            self.observer.log(kind, "scheduler", **detail)

    def add(self, process: AgentProcess) -> None:
        """Add a process to the ready queue."""
        if process not in self._ready:
            self._ready.append(process)
            self._log("scheduler_add", pid=process.pid)

    def remove(self, process: AgentProcess) -> None:
        """Remove a process from the ready queue."""
        if process in self._ready:
            self._ready.remove(process)
            self._log("scheduler_remove", pid=process.pid)

    def next(self) -> AgentProcess | None:
        """Return the ready process with the highest priority value."""
        ready = [p for p in self._ready if p.is_ready()]
        if not ready:
            return None
        process = max(ready, key=lambda p: p.priority)
        self._log("scheduler_pick", pid=process.pid, priority=process.priority)
        return process

    def tick(self) -> None:
        """No explicit tick needed for priority scheduling."""
        pass

    def __repr__(self) -> str:
        return f"PriorityScheduler(ready={[p.pid for p in self._ready]})"
