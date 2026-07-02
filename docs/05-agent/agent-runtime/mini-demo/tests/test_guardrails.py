"""Tests for guardrails."""

import pytest

from agent_runtime_mini.guardrails import GuardrailViolation, Guardrails


def test_forbidden_keyword_in_input():
    g = Guardrails(forbidden_keywords=["secret"])
    with pytest.raises(GuardrailViolation) as exc_info:
        g.check_input("Tell me the secret password")
    assert "secret" in str(exc_info.value)


def test_allowed_input():
    g = Guardrails(forbidden_keywords=["secret"])
    g.check_input("What is the weather?")


def test_max_tool_calls():
    g = Guardrails(max_tool_calls=2)
    tool_call = {
        "function": {"name": "search", "arguments": '{"query": "x"}'}
    }
    g.check_tool_call(tool_call, 1)
    g.check_tool_call(tool_call, 2)
    with pytest.raises(GuardrailViolation):
        g.check_tool_call(tool_call, 3)


def test_forbidden_path():
    g = Guardrails(forbidden_paths=["/etc"])
    tool_call = {
        "function": {"name": "read_file", "arguments": '{"path": "/etc/passwd"}'}
    }
    with pytest.raises(GuardrailViolation):
        g.check_tool_call(tool_call, 1)


def test_allowed_path():
    g = Guardrails(allowed_paths=["/tmp"])
    tool_call = {
        "function": {"name": "read_file", "arguments": '{"path": "/tmp/file.txt"}'}
    }
    g.check_tool_call(tool_call, 1)


def test_blocked_path_not_in_allowlist():
    g = Guardrails(allowed_paths=["/tmp"])
    tool_call = {
        "function": {"name": "read_file", "arguments": '{"path": "/etc/passwd"}'}
    }
    with pytest.raises(GuardrailViolation):
        g.check_tool_call(tool_call, 1)


def test_always_approve_write(monkeypatch):
    g = Guardrails(always_approve=True)
    tool_call = {
        "function": {"name": "write_file", "arguments": '{"path": "/tmp/x", "content": "x"}'}
    }
    assert g.request_approval(tool_call) is True


def test_denied_write(monkeypatch):
    g = Guardrails(always_approve=False)
    tool_call = {
        "function": {"name": "write_file", "arguments": '{"path": "/tmp/x", "content": "x"}'}
    }
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert g.request_approval(tool_call) is False
