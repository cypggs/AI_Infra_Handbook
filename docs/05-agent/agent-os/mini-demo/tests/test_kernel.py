"""Tests for the Agent OS kernel."""

import pytest

from agent_os_mini.kernel import Kernel
from agent_os_mini.process import ProcessState
from agent_os_mini.scheduler import PriorityScheduler


def noop_step(process):
    process.terminate()
    return "done"


def test_kernel_spawn_registers_process():
    kernel = Kernel()
    proc = kernel.spawn("test", noop_step)

    assert proc.pid == "p1"
    assert proc.role == "test"
    assert proc.is_ready()
    assert kernel.get_process("p1") is proc


def test_kernel_terminate_cleans_up_process():
    kernel = Kernel()
    proc = kernel.spawn("test", noop_step)
    kernel.terminate(proc)

    assert proc.is_terminated()
    assert proc not in kernel.scheduler._ready


def test_kernel_run_executes_until_done():
    kernel = Kernel()
    proc = kernel.spawn("test", noop_step)
    kernel.run()

    assert proc.is_terminated()
    assert len(kernel.running_processes()) == 0


def test_kernel_run_with_priority_scheduler():
    results = []

    def low_step(p):
        results.append("low")
        p.terminate()

    def high_step(p):
        results.append("high")
        p.terminate()

    scheduler = PriorityScheduler(observer=None)
    kernel = Kernel(scheduler=scheduler)
    kernel.spawn("low", low_step, priority=0)
    kernel.spawn("high", high_step, priority=10)

    kernel.run()

    assert results == ["high", "low"]


def test_kernel_step_once_removes_self_terminated_process():
    kernel = Kernel()
    proc = kernel.spawn("test", noop_step)
    kernel.step_once()

    assert proc.is_terminated()
    assert proc not in kernel.scheduler._ready
