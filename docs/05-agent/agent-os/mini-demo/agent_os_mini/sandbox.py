"""Capability/policy enforcement sandbox for the mini Agent OS.

The sandbox wraps tool calls so each process can only use an allow-listed set
of tools and is constrained by a per-process call budget. Exceeding the budget
raises a PolicyViolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class PolicyViolation(Exception):
    """Raised when a process violates a sandbox policy."""

    pass


@dataclass
class PolicyDecision:
    """Result of a sandbox authorization check."""

    allowed: bool
    reason: str = ""


class Sandbox:
    """Enforces per-process tool allowlists and call budgets."""

    def __init__(
        self,
        observer: Any,
        allowed_tools: set[str] | None = None,
        max_calls: int = 2,
    ) -> None:
        self.observer = observer
        self.allowed_tools = allowed_tools or set()
        self.max_calls = max_calls
        # Calls used per process ID.
        self._calls_used: dict[str, int] = {}
        # Registry of tool implementations keyed by tool name.
        self._tools: dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        """Register an implementation for a tool name."""
        self._tools[name] = fn

    def authorize(self, pid: str, tool_name: str) -> PolicyDecision:
        """Check whether pid may invoke tool_name under current policy."""
        if tool_name not in self.allowed_tools:
            return PolicyDecision(allowed=False, reason=f"tool {tool_name!r} not in allowlist")
        used = self._calls_used.get(pid, 0)
        if used >= self.max_calls:
            return PolicyDecision(allowed=False, reason=f"call budget exceeded ({used}/{self.max_calls})")
        return PolicyDecision(allowed=True)

    def call(self, pid: str, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Authorize and execute a tool call for pid.

        Raises PolicyViolation if the call is not allowed.
        """
        decision = self.authorize(pid, tool_name)
        self.observer.log(
            "sandbox_decision",
            "sandbox",
            pid=pid,
            tool=tool_name,
            allowed=decision.allowed,
            reason=decision.reason,
        )
        if not decision.allowed:
            raise PolicyViolation(decision.reason)

        if tool_name not in self._tools:
            raise PolicyViolation(f"tool {tool_name!r} has no registered implementation")

        self._calls_used[pid] = self._calls_used.get(pid, 0) + 1
        result = self._tools[tool_name](*args, **kwargs)
        self.observer.log(
            "sandbox_call",
            "sandbox",
            pid=pid,
            tool=tool_name,
            result=result,
            used=self._calls_used[pid],
        )
        return result

    def calls_used(self, pid: str) -> int:
        """Return the number of calls already consumed by pid."""
        return self._calls_used.get(pid, 0)

    def reset(self) -> None:
        """Reset call counters and tool registrations."""
        self._calls_used.clear()
        self._tools.clear()

    def __repr__(self) -> str:
        return f"Sandbox(allowed={self.allowed_tools}, max_calls={self.max_calls})"
