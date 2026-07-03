"""Tests for Plan DAG utilities."""
import pytest

from planning_mini.plan import Plan, Step


def test_topological_order_respects_dependencies():
    steps = [
        Step(id="a", tool="t", deps=[]),
        Step(id="b", tool="t", deps=["a"]),
        Step(id="c", tool="t", deps=["a", "b"]),
    ]
    plan = Plan(task="test", steps=steps)
    ordered = plan.topological_order()
    ids = [s.id for s in ordered]
    assert ids.index("a") < ids.index("b")
    assert ids.index("b") < ids.index("c")


def test_cycle_detection_raises():
    steps = [
        Step(id="a", tool="t", deps=["b"]),
        Step(id="b", tool="t", deps=["a"]),
    ]
    plan = Plan(task="test", steps=steps)
    with pytest.raises(ValueError, match="Cycle detected"):
        plan.topological_order()


def test_unknown_dependency_raises():
    steps = [Step(id="a", tool="t", deps=["missing"])]
    plan = Plan(task="test", steps=steps)
    with pytest.raises(ValueError, match="Unknown dependency"):
        plan.topological_order()


def test_ready_steps_only_when_dependencies_completed():
    steps = [
        Step(id="a", tool="t", deps=[]),
        Step(id="b", tool="t", deps=["a"]),
    ]
    plan = Plan(task="test", steps=steps)
    assert plan.ready_steps() == [steps[0]]
    steps[0].status = "completed"
    assert plan.ready_steps() == [steps[1]]
