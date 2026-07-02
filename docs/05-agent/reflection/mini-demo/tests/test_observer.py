"""Tests for the observer."""

from reflection_mini.observer import Observer


def test_record_appends_events():
    obs = Observer()
    obs.record("generate", iteration=0)
    obs.record("critique", iteration=0)

    assert len(obs.events) == 2
    assert obs.events[0]["event_type"] == "generate"
    assert obs.events[1]["iteration"] == 0


def test_rendered_trace_contains_events():
    obs = Observer()
    obs.record("generate", iteration=0)
    obs.record("finalize", reason="passed")

    rendered = obs.render()
    assert "Reflection trace:" in rendered
    assert "generate" in rendered
    assert "finalize" in rendered
    assert "reason='passed'" in rendered


def test_rendered_trace_has_tree_branches():
    obs = Observer()
    obs.record("a")
    obs.record("b")
    rendered = obs.render()

    assert "├──" in rendered or "└──" in rendered
