"""Agent OS Mini Demo package.

A tiny, CPU-runnable demonstration of operating-system-like abstractions
for coordinating multiple deterministic agents: kernel, scheduler, sandbox,
workspace, message bus, and observer.
"""

from .kernel import Kernel
from .process import AgentProcess, ProcessState
from .scheduler import RoundRobinScheduler, PriorityScheduler
from .sandbox import Sandbox, PolicyViolation
from .workspace import Workspace
from .message_bus import MessageBus
from .observer import Observer
from .demo import run_demo

__all__ = [
    "Kernel",
    "AgentProcess",
    "ProcessState",
    "RoundRobinScheduler",
    "PriorityScheduler",
    "Sandbox",
    "PolicyViolation",
    "Workspace",
    "MessageBus",
    "Observer",
    "run_demo",
]
