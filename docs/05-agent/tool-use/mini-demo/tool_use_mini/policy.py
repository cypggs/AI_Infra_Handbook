"""Policy enforcement for tool use loops."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class Policy:
    """Limits applied during a tool-use conversation."""

    allowed_tools: Optional[Set[str]] = None
    max_calls: int = 10
    timeout_budget_seconds: float = 60.0
    _call_count: int = field(default=0, repr=False)
    _start_time: float = field(default_factory=time.monotonic, repr=False)

    def reset(self) -> None:
        """Reset call count and timer."""
        self._call_count = 0
        self._start_time = time.monotonic()

    def check(self, tool_name: str) -> None:
        """Validate a proposed tool call against the policy.

        Raises:
            RuntimeError: if the tool is not allowed, the call budget is
                exhausted, or the timeout budget is exceeded.
        """
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            raise RuntimeError(f"Tool {tool_name!r} is not allowed by policy")

        if self._call_count >= self.max_calls:
            raise RuntimeError(f"Maximum tool call budget ({self.max_calls}) exceeded")

        elapsed = time.monotonic() - self._start_time
        if elapsed > self.timeout_budget_seconds:
            raise RuntimeError(
                f"Timeout budget ({self.timeout_budget_seconds}s) exceeded; elapsed={elapsed:.2f}s"
            )

        self._call_count += 1

    @property
    def call_count(self) -> int:
        """Number of tool calls that have passed the policy check so far."""
        return self._call_count

    @property
    def elapsed_seconds(self) -> float:
        """Elapsed time since the policy was created or reset."""
        return time.monotonic() - self._start_time
