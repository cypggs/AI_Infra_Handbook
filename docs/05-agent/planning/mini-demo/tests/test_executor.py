"""Tests for PlanExecutor scheduling and failure handling."""
from planning_mini.executor import PlanExecutor
from planning_mini.llm_client import MockLLMClient
from planning_mini.observer import Observer
from planning_mini.plan import Plan, Step
from planning_mini.planner import TaskPlanner
from planning_mini.policy import Policy
from planning_mini.replan_trigger import ReplanTrigger
from planning_mini.tool_registry import ToolRegistry


def test_executor_runs_dependent_steps_in_order():
    registry = ToolRegistry()
    observer = Observer()
    policy = Policy(allowed_tools=set(registry.tools.keys()))
    trigger = ReplanTrigger(policy)
    executor = PlanExecutor(registry, observer, trigger, policy, MockLLMClient())

    plan = Plan(
        task="sum",
        steps=[
            Step(id="flight", tool="search_flight", args={"origin": "北京", "dest": "东京"}),
            Step(id="hotel", tool="search_hotel", args={"city": "东京", "nights": 3}),
            Step(
                id="total",
                tool="calculate_total",
                args={"flight_price": "flight", "hotel_price": "hotel"},
                deps=["flight", "hotel"],
            ),
        ],
    )

    result = executor.run(plan)
    assert result["success"] is True
    assert plan.step_map()["total"].result == {"total": 5000}


def test_executor_marks_sold_out_as_failed():
    registry = ToolRegistry()
    registry.sold_out = True
    observer = Observer()
    policy = Policy(allowed_tools=set(registry.tools.keys()), max_replans=0)
    trigger = ReplanTrigger(policy)
    executor = PlanExecutor(registry, observer, trigger, policy, MockLLMClient())

    plan = Plan(
        task="trip",
        steps=[
            Step(id="flight", tool="search_flight", args={"origin": "北京", "dest": "东京"}),
        ],
    )

    result = executor.run(plan)
    assert result["success"] is False
    assert plan.step_map()["flight"].status == "failed"
