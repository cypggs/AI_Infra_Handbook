"""Tests for the AgentProcess lifecycle."""

from agent_os_mini.process import AgentProcess, ProcessState
from agent_os_mini.workspace import Workspace
from agent_os_mini.message_bus import MessageBus
from agent_os_mini.observer import Observer


def test_process_lifecycle_transitions():
    observer = Observer()
    workspace = Workspace()
    bus = MessageBus()

    def step_fn(process):
        process.terminate()
        return "ok"

    proc = AgentProcess("p1", "test", step_fn, workspace, bus, observer)

    assert proc.state == ProcessState.READY
    proc.step()
    assert proc.state == ProcessState.TERMINATED
    assert proc._steps_taken == 1


def test_process_step_logs_event():
    observer = Observer()
    proc = AgentProcess("p1", "test", lambda p: "x", Workspace(), MessageBus(), observer)

    proc.step()

    assert any(e.kind == "process_step" and e.detail["pid"] == "p1" for e in observer.events)


def test_terminated_process_step_returns_none():
    observer = Observer()
    proc = AgentProcess("p1", "test", lambda p: "x", Workspace(), MessageBus(), observer)
    proc.terminate()

    assert proc.step() is None
    assert proc.is_terminated()
