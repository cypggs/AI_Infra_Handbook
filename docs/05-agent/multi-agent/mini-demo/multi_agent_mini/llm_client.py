"""Deterministic LLM client that drives agent behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from multi_agent_mini.agent import Agent
    from multi_agent_mini.blackboard import Blackboard


class MockLLMClient:
    """A rule-based stand-in for a real LLM.

    Decisions are fully deterministic and depend on the acting agent's role
    and the current state of the shared blackboard.
    """

    def decide(
        self,
        agent: "Agent",
        blackboard: "Blackboard",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the next action for ``agent`` based on blackboard state."""
        role = agent.role
        has_facts = blackboard.read("facts") is not None
        has_draft = blackboard.read("draft") is not None
        has_review = blackboard.read("review") is not None

        if role == "researcher" and not has_facts:
            return {
                "action": "skill",
                "name": "search_facts",
                "args": {"query": "multi-agent collaboration"},
            }

        if role == "writer" and has_facts and not has_draft:
            return {
                "action": "skill",
                "name": "draft_section",
                "args": {"topic": "multi-agent best practices"},
            }

        if role == "reviewer" and has_draft and not has_review:
            return {
                "action": "skill",
                "name": "review_draft",
                "args": {},
            }

        if role == "coordinator" and has_facts and has_draft and has_review:
            return {"action": "finalize"}

        return {
            "action": "handoff",
            "to": self._next_agent(blackboard),
        }

    def _next_agent(self, blackboard: "Blackboard") -> str:
        if blackboard.read("facts") is None:
            return "researcher"
        if blackboard.read("draft") is None:
            return "writer"
        if blackboard.read("review") is None:
            return "reviewer"
        return "coordinator"
