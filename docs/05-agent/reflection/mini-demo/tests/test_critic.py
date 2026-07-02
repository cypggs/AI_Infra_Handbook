"""Tests for the critic agent."""

from reflection_mini.critic import CriticAgent
from reflection_mini.workspace import Workspace


def _make_workspace_with_draft(draft: str, iteration: int) -> Workspace:
    ws = Workspace()
    ws.write(f"draft_v{iteration}", draft)
    ws.write("latest_draft", draft)
    return ws


def test_critic_detects_issues_in_v1_draft():
    ws = _make_workspace_with_draft("Agent reflection is... v1", 0)
    critic = CriticAgent()
    critique = critic.evaluate(ws.read("latest_draft"), ws)

    assert "缺少具体例子" in critique
    assert "定义过于抽象" in critique
    assert ws.read("critique_v0") == critique
    assert ws.read("latest_critique") == critique


def test_critic_returns_lgtm_for_revised_draft():
    revised = (
        "Agent reflection is when an LLM-based agent critiques its own draft. "
        "For example, it checks for missing examples and revises."
    )
    ws = _make_workspace_with_draft(revised, 1)
    critic = CriticAgent()
    critique = critic.evaluate(ws.read("latest_draft"), ws)

    assert critique == ["LGTM"]
    assert ws.read("critique_v1") == critique
    assert ws.read("latest_critique") == critique
