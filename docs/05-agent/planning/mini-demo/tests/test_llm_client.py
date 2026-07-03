"""Tests for MockLLMClient deterministic planning."""
from planning_mini.llm_client import MockLLMClient


def test_generate_plan_is_deterministic():
    client = MockLLMClient()
    task = "帮我规划一次 北京→东京 3 天旅行，预算 8000 元"
    tools = ["search_flight", "search_hotel", "calculate_total", "generate_itinerary"]

    first = client.generate_plan(task, tools)
    second = client.generate_plan(task, tools)

    assert first == second
    assert first["steps"][0]["tool"] == "search_flight"


def test_replan_returns_alternative_flight():
    client = MockLLMClient()
    raw = client.replan(None, "search_flight", "sold_out")

    step_ids = [s["id"] for s in raw["steps"]]
    assert "search_flight_alt" in step_ids
    assert any(
        s["args"].get("direct") is True for s in raw["steps"] if s["id"] == "search_flight_alt"
    )
