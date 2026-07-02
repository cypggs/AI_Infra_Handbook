"""Tests for the evaluator agent."""

from reflection_mini.evaluator import Evaluator
from reflection_mini.workspace import Workspace


def _make_workspace_with_draft(draft: str, iteration: int) -> Workspace:
    ws = Workspace()
    ws.write(f"draft_v{iteration}", draft)
    ws.write("latest_draft", draft)
    return ws


def test_evaluator_scores_fail():
    ws = _make_workspace_with_draft("Agent reflection is... v1", 0)
    evaluator = Evaluator()
    result = evaluator.score(ws.read("latest_draft"), ["缺少具体例子"], ws)

    assert result == {"score": 0.4, "verdict": "fail"}
    assert ws.read("score_v0") == result
    assert ws.read("latest_score") == result


def test_evaluator_scores_pass():
    draft = (
        "Agent reflection is when an LLM-based agent critiques its own draft. "
        "For example, it checks for missing examples and revises."
    )
    ws = _make_workspace_with_draft(draft, 1)
    evaluator = Evaluator()
    result = evaluator.score(ws.read("latest_draft"), ["LGTM"], ws)

    assert result == {"score": 1.0, "verdict": "pass"}
    assert ws.read("score_v1") == result
    assert ws.read("latest_score") == result
