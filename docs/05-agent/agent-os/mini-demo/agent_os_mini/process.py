"""Agent process abstraction: lifecycle, state, and workspace binding."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Callable


class ProcessState(Enum):
    """Process lifecycle states."""

    READY = auto()
    RUNNING = auto()
    WAITING = auto()
    TERMINATED = auto()


class AgentProcess:
    """A lightweight agent process managed by the kernel.

    Each process has a unique ID, a role, private state, a reference to the
    shared workspace and message bus, and an execution step function.
    """

    def __init__(
        self,
        pid: str,
        role: str,
        step_fn: Callable[[AgentProcess], Any],
        workspace: Any,
        bus: Any,
        observer: Any,
        priority: int = 0,
    ) -> None:
        self.pid = pid
        self.role = role
        self.step_fn = step_fn
        self.workspace = workspace
        self.bus = bus
        self.observer = observer
        self.priority = priority
        self.state = ProcessState.READY
        self.result: Any = None
        self.metadata: dict[str, Any] = {}
        self._steps_taken = 0

    def step(self) -> Any:
        """Execute one agent step if the process is ready."""
        if self.state == ProcessState.TERMINATED:
            return None
        self.state = ProcessState.RUNNING
        self.observer.log("process_step", "process", pid=self.pid, role=self.role, step=self._steps_taken)
        try:
            outcome = self.step_fn(self)
        except Exception as exc:  # pragma: no cover - sandbox handles policy violations explicitly
            self.observer.log("process_error", "process", pid=self.pid, error=str(exc))
            raise
        self._steps_taken += 1
        # If the step function left the process running, return it to READY.
        if self.state == ProcessState.RUNNING:
            self.state = ProcessState.READY
        return outcome

    def terminate(self) -> None:
        """Move the process to the terminated state."""
        if self.state != ProcessState.TERMINATED:
            self.state = ProcessState.TERMINATED
            self.observer.log("process_terminate", "process", pid=self.pid, role=self.role)

    def is_ready(self) -> bool:
        """Return True if the process can be scheduled."""
        return self.state == ProcessState.READY

    def is_terminated(self) -> bool:
        """Return True if the process has finished."""
        return self.state == ProcessState.TERMINATED

    def __repr__(self) -> str:
        return f"AgentProcess(pid={self.pid!r}, role={self.role!r}, state={self.state.name})"
