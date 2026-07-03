"""Tests for ReplanTrigger decision logic."""
from planning_mini.observer import Observer
from planning_mini.plan import Plan, Step
from planning_mini.policy import Policy
from planning_mini.replan_trigger import ReplanTrigger


def _make_trigger(max_replans: int = 2) -> ReplanTrigger:
    policy = Policy(max_replans=max_replans)
    return ReplanTrigger(policy)


def test_sold_out_flight_triggers_replan():
    trigger = _make_trigger()
    plan = Plan(
        task="trip",
        steps=[
            Step(
                id="flight",
                tool="search_flight",
                status="failed",
                result={"status": "sold_out", "message": "sold out"},
            )
        ],
    )
    observer = Observer()
    assert trigger.decide(plan, observer, 0) == "replan"


def test_successful_plan_continues():
    trigger = _make_trigger()
    plan = Plan(
        task="trip",
        steps=[Step(id="flight", tool="search_flight", status="completed")],
    )
    observer = Observer()
    assert trigger.decide(plan, observer, 0) == "continue"


def test_max_replan_escalates_to_fail():
    trigger = _make_trigger(max_replans=1)
    plan = Plan(
        task="trip",
        steps=[
            Step(
                id="flight",
                tool="search_flight",
                status="failed",
                result={"status": "sold_out"},
            )
        ],
    )
    observer = Observer()
    assert trigger.decide(plan, observer, 1) == "fail"
