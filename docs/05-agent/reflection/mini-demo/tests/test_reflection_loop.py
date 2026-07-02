"""Tests for the reflection/revision loop."""

from reflection_mini.critic import CriticAgent
from reflection_mini.evaluator import Evaluator
from reflection_mini.generator import GeneratorAgent
from reflection_mini.llm_client import MockLLMClient
from reflection_mini.observer import Observer
from reflection_mini.reflection_loop import RevisionLoop
from reflection_mini.workspace import Workspace


def _make_loop(max_iterations: int = 3, score_threshold: float = 1.0):
    llm_client = MockLLMClient()
    return RevisionLoop(
        generator=GeneratorAgent(llm_client),
        critic=CriticAgent(llm_client),
        evaluator=Evaluator(llm_client),
        workspace=Workspace(),
        observer=Observer(),
        max_iterations=max_iterations,
        score_threshold=score_threshold,
    )


def test_loop_terminates_in_two_iterations():
    loop = _make_loop()
    result = loop.run("Explain Agent Reflection in one paragraph")

    assert result["iterations_run"] == 2
    assert result["passed"] is True
    assert "final_draft" in result["workspace"]
    assert "example" in result["workspace"]["final_draft"].lower()


def test_loop_respects_max_iterations():
    loop = _make_loop(max_iterations=1)
    result = loop.run("Explain Agent Reflection in one paragraph")

    assert result["iterations_run"] == 1
    assert result["passed"] is False
    assert "final_draft" in result["workspace"]


def test_observer_records_key_events():
    loop = _make_loop()
    loop.run("Explain Agent Reflection in one paragraph")

    event_types = [e["event_type"] for e in loop.observer.events]
    assert event_types[0] == "loop_start"
    assert "generate" in event_types
    assert "critique" in event_types
    assert "evaluate" in event_types
    assert event_types[-1] == "finalize"
