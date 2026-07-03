"""Mock LLM that generates deterministic answers from retrieved context."""

from __future__ import annotations

from dataclasses import dataclass

from rag_mini.documents import Chunk


@dataclass(frozen=True)
class Answer:
    """Generated answer with the source chunks that supported it."""

    text: str
    sources: list[Chunk]


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase alphanumeric tokens."""
    import re

    return set(re.findall(r"[a-z0-9]+", text.lower()))


class Generator:
    """Deterministic mock generator that answers from retrieved context.

    The generator does not call any external model. It matches query tokens
    against retrieved chunks and returns a hand-crafted answer when a known
    topic is detected; otherwise it returns a fallback response.
    """

    def __init__(self) -> None:
        """Initialize the generator with canned answers."""
        self._answers: dict[frozenset[str], str] = {
            frozenset({"return", "policy"}): (
                "Acme Corp accepts returns within thirty days of purchase with the "
                "original receipt. Items must be unused and in original packaging, "
                "and refunds are processed within five to seven business days."
            ),
            frozenset({"warranty"}): (
                "Acme electronics include a one-year limited warranty covering "
                "manufacturing defects. Customers can extend coverage to three years "
                "with Acme Care."
            ),
            frozenset({"products", "product"}): (
                "Acme Corp offers the Smart Widget, Power Bank, and Home Hub, all "
                "controlled through a single mobile app."
            ),
            frozenset({"history", "founded"}): (
                "Acme Corp was founded in 1985 by Jane Doe and John Smith and grew "
                "from a Seattle hardware shop into a global technology company."
            ),
        }

    def generate(self, query: str, context: list[Chunk]) -> Answer:
        """Generate an answer from the query and retrieved context.

        Args:
            query: User question.
            context: Top-k retrieved chunks.

        Returns:
            An Answer object containing the generated text and source chunks.
        """
        query_tokens = _tokenize(query)
        if not query_tokens or not context:
            return Answer(
                text="I don't have enough information to answer that.",
                sources=[],
            )

        # Score each canned topic by overlap with the query tokens.
        best_topic: frozenset[str] | None = None
        best_score = 0
        for topic in self._answers:
            score = len(query_tokens & topic)
            if score > best_score:
                best_score = score
                best_topic = topic

        if best_topic is not None and best_score > 0:
            return Answer(text=self._answers[best_topic], sources=context)

        # Fallback: try to extract an answer from the first context chunk.
        first_chunk = context[0].text
        return Answer(
            text=f"Based on the retrieved context: {first_chunk[:120]}...",
            sources=context,
        )
