"""Tests for the Observer."""

from multi_agent_mini.observer import Observer


def test_record_events():
    observer = Observer()
    observer.record("foo", x=1)
    observer.record("bar", y=2)
    assert len(observer.events) == 2
    assert observer.events[0]["type"] == "foo"
    assert observer.events[0]["data"]["x"] == 1


def test_render_contains_events():
    observer = Observer()
    observer.record("event_type", agent="researcher")
    text = observer.render()
    assert "Observer trace:" in text
    assert "event_type" in text
    assert "researcher" in text


def test_render_includes_timestamp():
    observer = Observer()
    observer.record("ping")
    text = observer.render()
    assert text.count(":") >= 1
