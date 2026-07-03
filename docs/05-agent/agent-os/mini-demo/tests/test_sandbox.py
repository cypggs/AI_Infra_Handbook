"""Tests for the capability/policy sandbox."""

import pytest

from agent_os_mini.sandbox import Sandbox, PolicyViolation
from agent_os_mini.observer import Observer


def test_sandbox_allows_registered_tool():
    observer = Observer()
    sandbox = Sandbox(observer, allowed_tools={"add"}, max_calls=2)
    sandbox.register_tool("add", lambda x, y: x + y)

    assert sandbox.call("p1", "add", 2, 3) == 5
    assert sandbox.calls_used("p1") == 1


def test_sandbox_blocks_disallowed_tool():
    observer = Observer()
    sandbox = Sandbox(observer, allowed_tools={"add"}, max_calls=2)
    sandbox.register_tool("add", lambda x, y: x + y)

    with pytest.raises(PolicyViolation):
        sandbox.call("p1", "subtract", 3, 2)


def test_sandbox_enforces_call_budget():
    observer = Observer()
    sandbox = Sandbox(observer, allowed_tools={"add"}, max_calls=2)
    sandbox.register_tool("add", lambda x, y: x + y)

    sandbox.call("p1", "add", 1, 1)
    sandbox.call("p1", "add", 2, 2)

    with pytest.raises(PolicyViolation):
        sandbox.call("p1", "add", 3, 3)


def test_sandbox_authorize_returns_decision():
    observer = Observer()
    sandbox = Sandbox(observer, allowed_tools={"add"}, max_calls=1)
    sandbox.register_tool("add", lambda x, y: x + y)

    assert sandbox.authorize("p1", "add").allowed is True
    assert sandbox.authorize("p1", "subtract").allowed is False

    sandbox.call("p1", "add", 1, 1)
    assert sandbox.authorize("p1", "add").allowed is False


def test_sandbox_logs_decisions():
    observer = Observer()
    sandbox = Sandbox(observer, allowed_tools={"add"}, max_calls=1)
    sandbox.register_tool("add", lambda x, y: x + y)
    sandbox.call("p1", "add", 1, 1)

    decisions = observer.filter("sandbox_decision")
    assert len(decisions) == 1
    assert decisions[0].detail["allowed"] is True
