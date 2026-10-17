"""Corrective retrieval grading (CRAG-style, arXiv:2401.15884).

Deterministic triage of hybrid retrieval results into Correct / Ambiguous /
Incorrect, based on agreement between the dense and keyword evidence
channels. In production systems the grader is usually a lightweight LLM or
cross-encoder; here we approximate it with score agreement so the demo
stays CPU-only and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_mini.retriever import RetrievalResult


class Grade(str, Enum):
    """Retrieval quality grade from CRAG (Corrective RAG)."""

    CORRECT = "correct"
    AMBIGUOUS = "ambiguous"
    INCORRECT = "incorrect"


@dataclass(frozen=True)
class Grading:
    """Result of grading a candidate list, with the recommended action."""

    grade: Grade
    action: str


def grade_results(results: list[RetrievalResult]) -> Grading:
    """Grade hybrid retrieval candidates by dense/keyword channel agreement.

    Rules (deterministic):
    - CORRECT: the top-ranked candidate is supported by both the dense and
      the keyword channel (both scores non-zero).
    - AMBIGUOUS: the head channels disagree, but at least one candidate in
      the list is supported by both channels.
    - INCORRECT: no candidate is supported by both channels.

    Args:
        results: Ranked candidates from ``Retriever.hybrid_search``.

    Returns:
        A ``Grading`` with the grade and the recommended pipeline action.
    """
    if not results:
        return Grading(Grade.INCORRECT, "empty recall: rewrite query or answer 'unknown'")

    def has_dual_support(result: RetrievalResult) -> bool:
        return result.dense_score > 0.0 and result.keyword_score > 0.0

    if has_dual_support(results[0]):
        return Grading(Grade.CORRECT, "use retrieved chunks as-is")
    if any(has_dual_support(r) for r in results):
        return Grading(
            Grade.AMBIGUOUS,
            "partial agreement: de-duplicate, expand, or supplement with extra knowledge",
        )
    return Grading(
        Grade.INCORRECT,
        "channels disagree: rewrite the query or fall back to 'unknown'",
    )
