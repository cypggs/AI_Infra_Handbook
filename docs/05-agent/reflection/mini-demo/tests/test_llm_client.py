"""Tests for the deterministic mock LLM client."""

import pytest

from reflection_mini.llm_client import MockLLMClient


@pytest.fixture
def client():
    return MockLLMClient()


def test_generate_draft_first_iteration_is_vague_and_has_v1(client):
    draft = client.generate_draft("Explain X", [], 0)
    assert "v1" in draft
    assert "example" not in draft.lower()


def test_generate_draft_later_iteration_includes_example(client):
    draft = client.generate_draft("Explain X", ["missing example"], 1)
    assert "example" in draft.lower()
    assert "v1" not in draft


def test_critique_flags_v1_draft(client):
    critique = client.critique("Agent reflection is... v1")
    assert "缺少具体例子" in critique
    assert "定义过于抽象" in critique
    assert "未说明何时停止" in critique


def test_critique_flags_missing_example(client):
    critique = client.critique("Agent reflection is the ability to think.")
    assert critique != ["LGTM"]
    assert "缺少具体例子" in critique


def test_critique_passes_draft_with_example(client):
    draft = "Agent reflection is when an agent checks its answer. For example, it adds examples."
    assert client.critique(draft) == ["LGTM"]


def test_evaluate_passes_when_lgtm_and_example(client):
    draft = "Agent reflection is great. For example, it revises."
    assert client.evaluate(draft, ["LGTM"]) == {"score": 1.0, "verdict": "pass"}


def test_evaluate_fails_when_critique_not_lgtm(client):
    draft = "Agent reflection is great. For example, it revises."
    assert client.evaluate(draft, ["needs work"]) == {"score": 0.4, "verdict": "fail"}


def test_evaluate_fails_when_example_missing(client):
    draft = "Agent reflection is great."
    assert client.evaluate(draft, ["LGTM"]) == {"score": 0.4, "verdict": "fail"}
