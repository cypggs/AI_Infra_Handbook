"""Tests for the deterministic LLM client."""

from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.llm_client import MockLLMClient


def _agent(role: str) -> Agent:
    return Agent(name=role, role=role)


def test_researcher_without_facts():
    board = Blackboard()
    decision = MockLLMClient().decide(_agent("researcher"), board)
    assert decision["action"] == "skill"
    assert decision["name"] == "search_facts"


def test_writer_with_facts_no_draft():
    board = Blackboard()
    board.write("facts", "facts")
    decision = MockLLMClient().decide(_agent("writer"), board)
    assert decision["action"] == "skill"
    assert decision["name"] == "draft_section"


def test_reviewer_with_draft_no_review():
    board = Blackboard()
    board.write("facts", "facts")
    board.write("draft", "draft")
    decision = MockLLMClient().decide(_agent("reviewer"), board)
    assert decision["action"] == "skill"
    assert decision["name"] == "review_draft"


def test_coordinator_when_all_ready():
    board = Blackboard()
    board.write("facts", "facts")
    board.write("draft", "draft")
    board.write("review", "review")
    decision = MockLLMClient().decide(_agent("coordinator"), board)
    assert decision["action"] == "finalize"


def test_handoff_to_researcher_when_missing_facts():
    board = Blackboard()
    decision = MockLLMClient().decide(_agent("coordinator"), board)
    assert decision["action"] == "handoff"
    assert decision["to"] == "researcher"


def test_handoff_to_writer_when_missing_draft():
    board = Blackboard()
    board.write("facts", "facts")
    decision = MockLLMClient().decide(_agent("coordinator"), board)
    assert decision["action"] == "handoff"
    assert decision["to"] == "writer"


def test_handoff_to_reviewer_when_missing_review():
    board = Blackboard()
    board.write("facts", "facts")
    board.write("draft", "draft")
    decision = MockLLMClient().decide(_agent("coordinator"), board)
    assert decision["action"] == "handoff"
    assert decision["to"] == "reviewer"
