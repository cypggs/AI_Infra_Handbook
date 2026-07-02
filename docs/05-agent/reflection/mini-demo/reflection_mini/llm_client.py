"""Deterministic mock LLM client for the reflection demo."""

from typing import Any


class MockLLMClient:
    """A rule-based LLM client with reproducible outputs.

    The client switches draft quality based on the iteration index and returns
    deterministic critiques and evaluations. It is intentionally simple so the
    demo runs on any CPU without API keys.
    """

    def generate_draft(
        self, request: str, prior_critique: list[str], iteration: int
    ) -> str:
        """Return a draft that improves once the agent has seen a critique.

        Args:
            request: The user's original instruction.
            prior_critique: Critique items from the previous iteration, if any.
            iteration: Zero-based revision index.

        Returns:
            A paragraph-length draft string.
        """
        del request  # Unused in the mock; kept for API symmetry.

        if iteration == 0:
            return (
                "Agent reflection is the ability of an agent to examine its own "
                "outputs and improve them. v1"
            )

        critique_note = ""
        if prior_critique:
            critique_note = (
                " After receiving feedback such as "
                + ", ".join(f"'{c}'" for c in prior_critique)
                + ", it revises."
            )

        return (
            "Agent reflection is when an LLM-based agent critiques its own draft "
            "and revises it to better satisfy the request. For example, after "
            "generating an answer, it checks for missing examples and revises."
            + critique_note
        )

    def critique(self, draft: str) -> list[str]:
        """Return deterministic critique items for a draft.

        Args:
            draft: The draft text to critique.

        Returns:
            A list of critique strings. ``["LGTM"]`` means the draft passes.
        """
        if "v1" in draft or "example" not in draft.lower():
            return ["缺少具体例子", "定义过于抽象", "未说明何时停止"]
        return ["LGTM"]

    def evaluate(self, draft: str, critique: list[str]) -> dict[str, Any]:
        """Score a draft/critique pair.

        Args:
            draft: The current draft.
            critique: The critique returned for the draft.

        Returns:
            A dictionary with ``score`` (float) and ``verdict`` (``"pass"`` or
            ``"fail"``).
        """
        if critique == ["LGTM"] and "example" in draft.lower():
            return {"score": 1.0, "verdict": "pass"}
        return {"score": 0.4, "verdict": "fail"}
