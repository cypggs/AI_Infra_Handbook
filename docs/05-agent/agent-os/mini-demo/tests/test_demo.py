"""End-to-end test for the Agent OS mini demo."""

from agent_os_mini.demo import run_demo
from agent_os_mini.sandbox import PolicyViolation
from agent_os_mini.kernel import Kernel
from agent_os_mini.process import AgentProcess, ProcessState


def test_demo_computes_correct_result():
    outcome = run_demo(2, 3, 4)

    assert outcome["result"] == 20
    assert outcome["workspace_state"]["final"] == 20


def test_demo_trace_includes_schedule_and_sandbox():
    outcome = run_demo(1, 1, 1)
    trace = outcome["trace"]

    assert "Schedule Trace" in trace
    assert "kernel_spawn" in trace
    assert "sandbox_decision" in trace


def test_demo_sandbox_blocks_extra_calls(capsys):
    """A worker that tries to call calculate three times must be blocked."""
    from agent_os_mini.scheduler import RoundRobinScheduler
    from agent_os_mini.sandbox import Sandbox
    from agent_os_mini.observer import Observer
    from agent_os_mini.workspace import Workspace
    from agent_os_mini.message_bus import MessageBus

    observer = Observer()
    workspace = Workspace()
    bus = MessageBus()
    sandbox = Sandbox(observer, allowed_tools={"calculate"}, max_calls=2)
    sandbox.register_tool("calculate", lambda op, x, y: x + y)
    kernel = Kernel(
        scheduler=RoundRobinScheduler(observer),
        sandbox=sandbox,
        observer=observer,
        workspace=workspace,
        bus=bus,
    )

    violations = []

    def greedy_step(process):
        try:
            sandbox.call(process.pid, "calculate", "add", 1, 1)
            sandbox.call(process.pid, "calculate", "add", 2, 2)
            sandbox.call(process.pid, "calculate", "add", 3, 3)
        except PolicyViolation as exc:
            violations.append(str(exc))
            process.terminate()

    worker = kernel.spawn("greedy", greedy_step)
    kernel.run()

    assert worker.is_terminated()
    assert len(violations) == 1
    blocked = observer.filter("sandbox_decision")
    assert any(not e.detail["allowed"] for e in blocked)


def test_demo_workers_terminate_after_task():
    outcome = run_demo(2, 3, 4)
    observer = outcome["observer"]

    terminate_events = observer.filter("process_terminate")
    terminated_pids = {e.detail["pid"] for e in terminate_events}

    assert len(terminated_pids) >= 3  # coordinator + adder + multiplier
