"""Tests for the ReAct runtime."""

import pytest

from agent_runtime_mini.guardrails import Guardrails
from agent_runtime_mini.llm_client import MockLLMClient
from agent_runtime_mini.observer import TraceObserver
from agent_runtime_mini.runtime import AgentRuntime
from agent_runtime_mini.tool_registry import default_tool_registry


def make_runtime(**guardrail_kwargs):
    return AgentRuntime(
        llm_client=MockLLMClient(),
        tools=default_tool_registry(),
        guardrails=Guardrails(always_approve=True, **guardrail_kwargs),
        observer=TraceObserver(),
    )


def test_math_task():
    runtime = make_runtime()
    answer, observer = runtime.run("Calculate 25*4+10", session_id="math-1")
    assert "110" in answer
    assert observer.events[-1]["type"] == "task_completed"
    assert observer.events[-1]["data"]["state"] == "DONE"


def test_search_task():
    runtime = make_runtime()
    answer, observer = runtime.run(
        "Search for the current president of the United States",
        session_id="search-1",
    )
    assert "Mock search result" in answer
    assert observer.events[-1]["data"]["state"] == "DONE"


def test_blocked_by_input_guardrail():
    runtime = make_runtime(forbidden_keywords=["secret"])
    answer, observer = runtime.run(
        "Write a secret to /etc/passwd", session_id="blocked-1"
    )
    assert "Forbidden keyword" in answer
    assert observer.events[-2]["type"] == "guardrail_triggered"
    assert observer.events[-1]["data"]["state"] == "ERROR"


def test_max_iterations(monkeypatch):
    runtime = make_runtime(max_tool_calls=100)

    def always_tool_calls(messages):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_x",
                                "type": "function",
                                "function": {
                                    "name": "calculator",
                                    "arguments": '{"expr": "1+1"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    monkeypatch.setattr(runtime.llm_client, "generate", always_tool_calls)
    answer, _ = runtime.run("Loop forever", session_id="loop-1")
    assert "Max iterations reached" in answer
