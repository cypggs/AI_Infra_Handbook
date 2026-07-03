"""Tests for TaskPlanner plan construction and validation."""
import pytest

from planning_mini.llm_client import MockLLMClient
from planning_mini.planner import TaskPlanner
from planning_mini.tool_registry import ToolRegistry


def test_planner_returns_expected_steps_for_travel_task():
    registry = ToolRegistry()
    planner = TaskPlanner(MockLLMClient(), registry)
    plan = planner.create_plan("帮我规划一次 北京→东京 3 天旅行，预算 8000 元")

    ids = [s.id for s in plan.steps]
    assert ids == [
        "search_flight",
        "search_hotel",
        "calculate_total",
        "check_policy",
        "generate_itinerary",
    ]


def test_planner_rejects_unknown_tool():
    class BadLLM:
        def generate_plan(self, task, tools):
            return {"steps": [{"id": "x", "tool": "unknown_tool", "args": {}, "deps": []}]}

    registry = ToolRegistry()
    planner = TaskPlanner(BadLLM(), registry)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unknown tool 'unknown_tool'"):
        planner.create_plan("anything")
