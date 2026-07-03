"""End-to-end demo: multi-agent calculation coordinated by a tiny Agent OS.

Scenario:
    A CoordinatorAgent is asked to compute (a + b) * c for a=2, b=3, c=4.
    It spawns an AdderAgent (a + b) and a MultiplierAgent (result * c).
    Workers run inside a sandbox that only permits the ``calculate`` tool
    and limits each worker to two calls. Results flow through the workspace
    and message bus. The coordinator collects the final answer and shuts
    down all processes.
"""

from __future__ import annotations

from typing import Any

from .kernel import Kernel
from .process import AgentProcess, ProcessState
from .sandbox import Sandbox
from .scheduler import RoundRobinScheduler


def _calculate(operation: str, x: float, y: float) -> float:
    """The only tool workers are allowed to invoke."""
    if operation == "add":
        return x + y
    if operation == "multiply":
        return x * y
    raise ValueError(f"unsupported operation: {operation}")


def _make_coordinator_step(kernel: Kernel, a: float, b: float, c: float) -> Any:
    """Build the coordinator's state-machine step function."""

    def step(process: AgentProcess) -> Any:
        phase = process.metadata.setdefault("phase", "init")
        process.workspace.write_shared("a", a)
        process.workspace.write_shared("b", b)
        process.workspace.write_shared("c", c)

        if phase == "init":
            # Post the addition subtask and spawn the adder.
            process.workspace.write_shared("task", "add")
            adder = kernel.spawn("adder", _make_adder_step(kernel))
            process.metadata["adder_pid"] = adder.pid
            process.metadata["phase"] = "wait_add"
            process.state = ProcessState.WAITING
            return {"action": "spawn_adder", "adder": adder.pid}

        if phase == "wait_add":
            # Wait for the adder to deliver the sum.
            for msg in process.bus.inbox(process.pid):
                if msg.topic == "add_result":
                    intermediate = msg.payload
                    process.workspace.write_shared("intermediate", intermediate)
                    process.bus.clear_inbox(process.pid)
                    # Post the multiplication subtask.
                    process.workspace.write_shared("task", "multiply")
                    multiplier = kernel.spawn("multiplier", _make_multiplier_step(kernel))
                    process.metadata["multiplier_pid"] = multiplier.pid
                    process.metadata["phase"] = "wait_multiply"
                    process.state = ProcessState.WAITING
                    return {"action": "spawn_multiplier", "sum": intermediate}
            process.state = ProcessState.WAITING
            return {"action": "waiting_for_adder"}

        if phase == "wait_multiply":
            for msg in process.bus.inbox(process.pid):
                if msg.topic == "multiply_result":
                    final = msg.payload
                    process.workspace.write_shared("final", final)
                    process.result = final
                    process.metadata["phase"] = "done"
                    kernel.terminate_all()
                    return {"action": "done", "result": final}
            process.state = ProcessState.WAITING
            return {"action": "waiting_for_multiplier"}

        # phase == "done"
        kernel.terminate_all()
        return {"action": "already_done", "result": process.result}

    return step


def _make_adder_step(kernel: Kernel) -> Any:
    """Build the adder worker's step function."""

    def step(process: AgentProcess) -> Any:
        a = process.workspace.read_shared("a")
        b = process.workspace.read_shared("b")
        # Sandbox only allows the ``calculate`` tool.
        total = kernel.sandbox.call(process.pid, "calculate", "add", a, b)
        process.workspace.write_shared("intermediate", total)
        # Report the result back to the coordinator via the message bus.
        coordinator = next(
            (p for p in kernel._processes.values() if p.role == "coordinator"),
            None,
        )
        if coordinator is not None:
            process.bus.send(process.pid, coordinator.pid, "add_result", total)
        process.terminate()
        return {"action": "add", "result": total}

    return step


def _make_multiplier_step(kernel: Kernel) -> Any:
    """Build the multiplier worker's step function."""

    def step(process: AgentProcess) -> Any:
        intermediate = process.workspace.read_shared("intermediate")
        c = process.workspace.read_shared("c")
        product = kernel.sandbox.call(process.pid, "calculate", "multiply", intermediate, c)
        process.workspace.write_shared("final", product)
        coordinator = next(
            (p for p in kernel._processes.values() if p.role == "coordinator"),
            None,
        )
        if coordinator is not None:
            process.bus.send(process.pid, coordinator.pid, "multiply_result", product)
        process.terminate()
        return {"action": "multiply", "result": product}

    return step


def _format_trace(observer: Any) -> str:
    """Return a human-readable schedule trace."""
    lines = ["=== Schedule Trace ==="]
    for event in observer.events:
        detail = " ".join(f"{k}={v}" for k, v in event.detail.items())
        lines.append(f"[{event.source}] {event.kind}: {detail}")
    return "\n".join(lines)


def _format_sandbox_decisions(observer: Any) -> str:
    """Return a human-readable list of sandbox decisions."""
    lines = ["=== Sandbox Decisions ==="]
    for event in observer.filter("sandbox_decision"):
        detail = event.detail
        status = "ALLOW" if detail.get("allowed") else "BLOCK"
        lines.append(
            f"{status} pid={detail.get('pid')} tool={detail.get('tool')} reason={detail.get('reason')}"
        )
    return "\n".join(lines)


def run_demo(a: float = 2, b: float = 3, c: float = 4) -> dict[str, Any]:
    """Run the multi-agent calculation demo and print the outcome.

    Returns a dictionary containing the final result, schedule trace, sandbox
    decisions, and workspace state for programmatic inspection.
    """
    from .observer import Observer
    from .workspace import Workspace
    from .message_bus import MessageBus

    observer = Observer()
    workspace = Workspace()
    bus = MessageBus()
    sandbox = Sandbox(observer, allowed_tools={"calculate"}, max_calls=2)
    sandbox.register_tool("calculate", _calculate)
    scheduler = RoundRobinScheduler(observer)
    kernel = Kernel(
        scheduler=scheduler,
        sandbox=sandbox,
        observer=observer,
        workspace=workspace,
        bus=bus,
    )

    coordinator = kernel.spawn(
        "coordinator",
        _make_coordinator_step(kernel, a, b, c),
        priority=1,
    )
    coordinator.workspace.write_private(coordinator.pid, "task", f"calculate ({a}+{b})*{c}")

    kernel.run(max_steps=50)

    trace = _format_trace(observer)
    sandbox_decisions = _format_sandbox_decisions(observer)
    workspace_state = workspace.shared_snapshot()
    final = workspace_state.get("final")

    print(trace)
    print()
    print(sandbox_decisions)
    print()
    print("=== Workspace State ===")
    for key, value in workspace_state.items():
        print(f"  {key} = {value}")
    print()
    print(f"Final answer: {final}")

    return {
        "result": final,
        "trace": trace,
        "sandbox_decisions": sandbox_decisions,
        "workspace_state": workspace_state,
        "observer": observer,
    }


if __name__ == "__main__":
    run_demo()
