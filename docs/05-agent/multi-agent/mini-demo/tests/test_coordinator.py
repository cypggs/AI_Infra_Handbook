"""Tests for the Coordinator."""

from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.bus import MessageBus
from multi_agent_mini.coordinator import Coordinator
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.observer import Observer
from multi_agent_mini.skills import (
    draft_section,
    finalize_post,
    handoff_to,
    review_draft,
    search_facts,
)


def _make_team() -> list[Agent]:
    agents = [
        Agent(name="coordinator", role="coordinator"),
        Agent(name="researcher", role="researcher"),
        Agent(name="writer", role="writer"),
        Agent(name="reviewer", role="reviewer"),
    ]
    for agent in agents:
        for skill in (search_facts, draft_section, review_draft, finalize_post, handoff_to):
            agent.register_skill(skill.__name__, skill)
    return agents


def test_handoff_mode_completes():
    coordinator = Coordinator(
        agents=_make_team(),
        mode="handoff",
        blackboard=Blackboard(),
        bus=MessageBus(),
        observer=Observer(),
        llm_client=MockLLMClient(),
    )
    result = coordinator.run("Write a post.")
    bb = result["blackboard"]
    assert bb.get("facts")
    assert bb.get("draft")
    assert bb.get("review")
    assert bb.get("final_post")
    assert result["turns"] <= 10


def test_round_robin_mode_completes():
    coordinator = Coordinator(
        agents=_make_team(),
        mode="round_robin",
        blackboard=Blackboard(),
        bus=MessageBus(),
        observer=Observer(),
        llm_client=MockLLMClient(),
    )
    result = coordinator.run("Write a post.")
    bb = result["blackboard"]
    assert bb.get("facts")
    assert bb.get("draft")
    assert bb.get("review")
    assert bb.get("final_post")


def test_invalid_mode_raises():
    try:
        Coordinator(agents=[], mode="free_for_all")
    except ValueError as exc:
        assert "Unsupported mode" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_run_records_trace_events():
    coordinator = Coordinator(
        agents=_make_team(),
        mode="handoff",
        blackboard=Blackboard(),
        bus=MessageBus(),
        observer=Observer(),
        llm_client=MockLLMClient(),
    )
    result = coordinator.run("Write a post.")
    types = [e["type"] for e in result["trace"]]
    assert "run_started" in types
    assert "finalized" in types
    assert "skill_executed" in types
