"""Tests for the Policy enforcement module."""

import time

import pytest

from tool_use_mini.policy import Policy


def test_allowed_tool_passes_and_counts():
    """An allowed tool call consumes budget and increments the counter."""
    policy = Policy(allowed_tools={"get_weather"}, max_calls=3)
    policy.check("get_weather")
    policy.check("get_weather")
    assert policy.call_count == 2


def test_disallowed_tool_raises():
    """A tool outside the allowed set is rejected."""
    policy = Policy(allowed_tools={"get_weather"})
    with pytest.raises(RuntimeError, match="not allowed by policy"):
        policy.check("delete_user")


def test_call_budget_exceeded():
    """Calls beyond max_calls are rejected."""
    policy = Policy(max_calls=2)
    policy.check("a")
    policy.check("a")
    with pytest.raises(RuntimeError, match="Maximum tool call budget"):
        policy.check("a")
    assert policy.call_count == 2


def test_timeout_budget_exceeded():
    """Calls after the timeout budget are rejected."""
    policy = Policy(timeout_budget_seconds=5.0)
    # Simulate that the budget window has already elapsed.
    policy._start_time = time.monotonic() - 10.0
    with pytest.raises(RuntimeError, match="Timeout budget"):
        policy.check("a")
    assert policy.call_count == 0


def test_unlimited_tools_when_allowed_is_none():
    """allowed_tools=None means any tool may be called."""
    policy = Policy(allowed_tools=None)
    policy.check("anything")
    policy.check("something_else")
    assert policy.call_count == 2


def test_reset_restores_budget():
    """Reset clears the call counter and restarts the timer."""
    policy = Policy(max_calls=1, timeout_budget_seconds=5.0)
    policy.check("a")
    assert policy.call_count == 1
    with pytest.raises(RuntimeError):
        policy.check("a")

    policy.reset()
    assert policy.call_count == 0
    policy.check("a")  # budget available again
    assert policy.call_count == 1
