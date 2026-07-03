"""Simple score-based reranker for retrieved candidates."""

from __future__ import annotations

from dataclasses import dataclass

from rag_mini.documents import Chunk
from rag_mini.retriever import RetrievalResult


def _token_overlap(query: str, text: str) -> float:
    """Compute normalized token overlap between query and text.

    Args:
        query: User query.
        text: Chunk text.

    Returns:
        Jaccard-like overlap score in the range [0, 1].
    """
    import re

    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / len(query_tokens)


@dataclass(frozen=True)
class RankedResult:
    """A reranked result with its final score and provenance."""

    chunk: Chunk
    final_score: float
    dense_score: float
    keyword_score: float
    overlap_score: float


class Reranker:
    """Simple deterministic reranker combining dense, keyword, and overlap scores.

    The reranker mimics a lightweight cross-encoder by blending the retrieval
    scores with a token-overlap feature. All weights are fixed and deterministic.
    """

    def __init__(
        self,
        dense_weight: float = 0.4,
        keyword_weight: float = 0.3,
        overlap_weight: float = 0.3,
    ) -> None:
        """Initialize the reranker.

        Args:
            dense_weight: Weight for the dense retrieval score.
            keyword_weight: Weight for the keyword retrieval score.
            overlap_weight: Weight for the token overlap score.
        """
        total = dense_weight + keyword_weight + overlap_weight
        self._dense_weight = dense_weight / total
        self._keyword_weight = keyword_weight / total
        self._overlap_weight = overlap_weight / total

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RankedResult]:
        """Rerank retrieval results for the given query.

        Args:
            query: User query.
            results: Retrieval results from dense, keyword, or hybrid search.

        Returns:
            Results sorted by final score, highest first.
        """
        if not results:
            return []

        # Normalize dense and keyword scores within the result set.
        max_dense = max((r.dense_score for r in results), default=1.0) or 1.0
        max_keyword = max((r.keyword_score for r in results), default=1.0) or 1.0

        ranked: list[RankedResult] = []
        for r in results:
            overlap = _token_overlap(query, r.chunk.text)
            dense_norm = r.dense_score / max_dense
            keyword_norm = r.keyword_score / max_keyword
            final_score = (
                self._dense_weight * dense_norm
                + self._keyword_weight * keyword_norm
                + self._overlap_weight * overlap
            )
            ranked.append(
                RankedResult(
                    chunk=r.chunk,
                    final_score=final_score,
                    dense_score=r.dense_score,
                    keyword_score=r.keyword_score,
                    overlap_score=overlap,
                )
            )

        ranked.sort(key=lambda x: x.final_score, reverse=True)
        return ranked
