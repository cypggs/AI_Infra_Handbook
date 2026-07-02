"""Evaluator agent that scores draft/critique pairs."""

import re
from typing import Any

from reflection_mini.llm_client import MockLLMClient
from reflection_mini.workspace import Workspace


class Evaluator:
    """Agent responsible for scoring drafts and deciding when to stop."""

    def __init__(self, llm_client: MockLLMClient | None = None) -> None:
        """Create an evaluator with an optional mock client.

        Args:
            llm_client: Client used to evaluate drafts. A new
                :class:`MockLLMClient` is created if none is provided.
        """
        self.llm_client = llm_client or MockLLMClient()

    @staticmethod
    def _detect_iteration(workspace: Workspace) -> int:
        """Infer the current iteration from draft keys in the workspace."""
        iterations: list[int] = []
        for key in workspace.keys():
            match = re.fullmatch(r"draft_v(\d+)", key)
            if match:
                iterations.append(int(match.group(1)))
        return max(iterations) if iterations else 0

    def score(
        self, draft: str, critique: list[str], workspace: Workspace
    ) -> dict[str, Any]:
        """Evaluate ``draft`` against ``critique`` and record the result.

        The score is written to both ``score_v{iteration}`` and
        ``latest_score``.

        Args:
            draft: The current draft.
            critique: The critique applied to the draft.
            workspace: Shared workspace for artifacts.

        Returns:
            A dictionary with ``score`` and ``verdict``.
        """
        result = self.llm_client.evaluate(draft, critique)
        iteration = self._detect_iteration(workspace)

        workspace.write(f"score_v{iteration}", result)
        workspace.write("latest_score", result)

        return result
