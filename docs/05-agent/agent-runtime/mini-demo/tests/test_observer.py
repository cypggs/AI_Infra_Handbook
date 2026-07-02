"""Tests for trace observability."""

from agent_runtime_mini.observer import TraceObserver


def test_record_events():
    observer = TraceObserver()
    observer.record("task_received", session_id="s1", task="hello")
    observer.record("tool_executed", tool_name="calculator", result=42)
    assert len(observer.events) == 2
    assert observer.events[0]["type"] == "task_received"
    assert observer.events[0]["data"]["session_id"] == "s1"


def test_render_contains_events():
    observer = TraceObserver()
    observer.record("task_received", session_id="s2", task="hi")
    text = observer.render()
    assert "Trace:" in text
    assert "task_received" in text
    assert "s2" in text
