"""Generator agent that produces drafts using the mock LLM client."""

from reflection_mini.llm_client import MockLLMClient
from reflection_mini.workspace import Workspace


class GeneratorAgent:
    """Agent responsible for producing drafts from a user request."""

    def __init__(self, llm_client: MockLLMClient | None = None) -> None:
        """Create a generator with an optional mock client.

        Args:
            llm_client: Client used to generate drafts. A new
                :class:`MockLLMClient` is created if none is provided.
        """
        self.llm_client = llm_client or MockLLMClient()

    def produce(self, request: str, workspace: Workspace, iteration: int = 0) -> str:
        """Generate a draft and store it in the workspace.

        The draft is written to both ``draft_v{iteration}`` and
        ``latest_draft``.

        Args:
            request: The user's instruction.
            workspace: Shared workspace for drafts and metadata.
            iteration: Zero-based revision index.

        Returns:
            The generated draft string.
        """
        prior_critique: list[str] = []
        if "latest_critique" in workspace.keys():
            prior_critique = workspace.read("latest_critique")
            if not isinstance(prior_critique, list):
                prior_critique = []

        draft = self.llm_client.generate_draft(request, prior_critique, iteration)

        workspace.write(f"draft_v{iteration}", draft)
        workspace.write("latest_draft", draft)

        return draft
