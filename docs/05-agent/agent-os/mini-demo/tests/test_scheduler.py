"""Tests for the scheduler implementations."""

from agent_os_mini.process import AgentProcess, ProcessState
from agent_os_mini.scheduler import RoundRobinScheduler, PriorityScheduler
from agent_os_mini.observer import Observer
from agent_os_mini.workspace import Workspace
from agent_os_mini.message_bus import MessageBus


def make_process(pid, role, priority=0):
    return AgentProcess(pid, role, lambda p: None, Workspace(), MessageBus(), Observer(), priority=priority)


def test_round_robin_ordering():
    observer = Observer()
    scheduler = RoundRobinScheduler(observer)
    p1 = make_process("p1", "a")
    p2 = make_process("p2", "b")
    scheduler.add(p1)
    scheduler.add(p2)

    assert scheduler.next() is p1
    assert scheduler.next() is p2
    assert scheduler.next() is p1


def test_round_robin_skips_non_ready_processes():
    observer = Observer()
    scheduler = RoundRobinScheduler(observer)
    p1 = make_process("p1", "a")
    p2 = make_process("p2", "b")
    p1.state = ProcessState.WAITING
    scheduler.add(p1)
    scheduler.add(p2)

    assert scheduler.next() is p2
    assert scheduler.next() is p2


def test_priority_scheduler_picks_highest_priority():
    observer = Observer()
    scheduler = PriorityScheduler(observer)
    low = make_process("low", "a", priority=1)
    high = make_process("high", "b", priority=10)
    scheduler.add(low)
    scheduler.add(high)

    assert scheduler.next() is high


def test_scheduler_remove():
    observer = Observer()
    scheduler = RoundRobinScheduler(observer)
    p1 = make_process("p1", "a")
    scheduler.add(p1)
    scheduler.remove(p1)

    assert scheduler.next() is None
