"""Tests for built-in skills."""

from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.skills import (
    draft_section,
    finalize_post,
    handoff_to,
    review_draft,
    search_facts,
)


def test_search_facts_writes_facts():
    board = Blackboard()
    result = search_facts("multi-agent", board)
    assert "Facts collected" in result
    facts = board.read("facts")
    assert facts is not None
    assert "modularity" in facts


def test_draft_section_writes_draft():
    board = Blackboard()
    search_facts("topic", board)
    result = draft_section("Best Practices", board)
    assert "Draft written" in result
    draft = board.read("draft")
    assert "# Best Practices" in draft
    assert "Draft:" in draft


def test_review_draft_writes_review():
    board = Blackboard()
    search_facts("topic", board)
    draft_section("Topic", board)
    result = review_draft(board)
    assert "Review complete" in result
    review = board.read("review")
    assert "Review comments" in review


def test_finalize_post_writes_final_post():
    board = Blackboard()
    search_facts("topic", board)
    draft_section("Topic", board)
    review_draft(board)
    result = finalize_post(board)
    assert "Final post written" in result
    post = board.read("final_post")
    assert "# Multi-Agent Collaboration Best Practices" in post
    assert "Finalized and ready" in post


def test_handoff_to_records_next_agent():
    board = Blackboard()
    result = handoff_to("writer", board)
    assert result == "Handoff to writer."
    assert board.read("next_agent") == "writer"
    assert board.scope("next_agent") == "private"
