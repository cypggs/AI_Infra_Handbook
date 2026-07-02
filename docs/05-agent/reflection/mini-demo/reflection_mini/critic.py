"""Critic agent that critiques drafts."""

import re

from reflection_mini.llm_client import MockLLMClient
from reflection_mini.workspace import Workspace


class CriticAgent:
    """Agent responsible for critiquing drafts produced by the generator."""

    def __init__(self, llm_client: MockLLMClient | None = None) -> None:
        """Create a critic with an optional mock client.

        Args:
            llm_client: Client used to critique drafts. A new
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

    def evaluate(self, draft: str, workspace: Workspace) -> list[str]:
        """Critique ``draft`` and store the result in the workspace.

        The critique is written to both ``critique_v{iteration}`` and
        ``latest_critique``.

        Args:
            draft: The draft text to critique.
            workspace: Shared workspace for artifacts.

        Returns:
            A list of critique strings.
        """
        critique = self.llm_client.critique(draft)
        iteration = self._detect_iteration(workspace)

        workspace.write(f"critique_v{iteration}", critique)
        workspace.write("latest_critique", critique)

        return critique
