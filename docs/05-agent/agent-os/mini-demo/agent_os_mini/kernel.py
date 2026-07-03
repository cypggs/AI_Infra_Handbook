"""Tiny Agent OS kernel: spawn, schedule, terminate, and registry.

The Kernel owns the workspace, message bus, sandbox, scheduler, and observer.
It provides the main `run()` loop that steps ready processes until the demo
scenario completes.
"""

from __future__ import annotations

from typing import Any, Callable

from .message_bus import MessageBus
from .observer import Observer
from .process import AgentProcess, ProcessState
from .sandbox import Sandbox
from .scheduler import RoundRobinScheduler
from .workspace import Workspace


class Kernel:
    """Mini kernel that orchestrates agent processes."""

    def __init__(
        self,
        scheduler: Any | None = None,
        sandbox: Sandbox | None = None,
        observer: Observer | None = None,
        workspace: Workspace | None = None,
        bus: MessageBus | None = None,
    ) -> None:
        self.observer = observer or Observer()
        self.workspace = workspace or Workspace()
        self.bus = bus or MessageBus()
        self.bus._on_deliver = self._wakeup_process
        self.sandbox = sandbox or Sandbox(self.observer)
        self.scheduler = scheduler or RoundRobinScheduler(self.observer)
        self._processes: dict[str, AgentProcess] = {}
        self._pid_counter = 0

    def _wakeup_process(self, pid: str) -> None:
        """Wake a waiting process when a message is delivered to it."""
        process = self._processes.get(pid)
        if process is not None and process.state == ProcessState.WAITING:
            process.state = ProcessState.READY
            self.observer.log("kernel_wakeup", "kernel", pid=pid)

    def _next_pid(self) -> str:
        self._pid_counter += 1
        return f"p{self._pid_counter}"

    def spawn(
        self,
        role: str,
        step_fn: Callable[[AgentProcess], Any],
        priority: int = 0,
    ) -> AgentProcess:
        """Create and register a new agent process."""
        pid = self._next_pid()
        process = AgentProcess(
            pid=pid,
            role=role,
            step_fn=step_fn,
            workspace=self.workspace,
            bus=self.bus,
            observer=self.observer,
            priority=priority,
        )
        self._processes[pid] = process
        self.bus.register(pid)
        self.scheduler.add(process)
        self.observer.log("kernel_spawn", "kernel", pid=pid, role=role, priority=priority)
        return process

    def terminate(self, process: AgentProcess) -> None:
        """Terminate a process and clean up its scheduler entry."""
        process.terminate()
        self.scheduler.remove(process)
        self.bus.unregister(process.pid)
        self.observer.log("kernel_terminate", "kernel", pid=process.pid)

    def terminate_all(self) -> None:
        """Terminate every running process."""
        for process in list(self._processes.values()):
            self.terminate(process)

    def get_process(self, pid: str) -> AgentProcess | None:
        """Look up a process by ID."""
        return self._processes.get(pid)

    def running_processes(self) -> list[AgentProcess]:
        """Return all non-terminated processes."""
        return [p for p in self._processes.values() if not p.is_terminated()]

    def step_once(self) -> Any:
        """Run a single scheduler step: pick next process and execute it."""
        process = self.scheduler.next()
        if process is None:
            return None
        self.observer.log("kernel_schedule", "kernel", pid=process.pid, role=process.role)
        outcome = process.step()
        if process.is_terminated():
            self.scheduler.remove(process)
        self.observer.log("kernel_step_done", "kernel", pid=process.pid, outcome=outcome)
        return outcome

    def run(self, max_steps: int = 100) -> Any:
        """Run the scheduling loop until no ready processes remain or max_steps is hit."""
        final_outcome = None
        for step in range(max_steps):
            if not any(p.is_ready() for p in self._processes.values()):
                break
            final_outcome = self.step_once()
        self.observer.log("kernel_run_complete", "kernel", steps=step + 1)
        return final_outcome

    def __repr__(self) -> str:
        return f"Kernel(processes={len(self._processes)})"
