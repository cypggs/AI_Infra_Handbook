from __future__ import annotations

from typing import List, Tuple

from agent_memory_mini.embedder import DeterministicEmbedder, tokenize
from agent_memory_mini.vector_store import (
    InMemoryVectorStore,
    MemoryRecord,
    _cosine_similarity,
)


class MemoryRetriever:
    """Retrieves memories using vector similarity, keyword overlap, or both.

    The hybrid mode combines cosine similarity with a simple Jaccard-style
    token-overlap score. This is a miniature version of production hybrid
    search (dense vectors + sparse BM25/keyword indexes).
    """

    def __init__(
        self,
        embedder: DeterministicEmbedder,
        vector_store: InMemoryVectorStore,
    ):
        self.embedder = embedder
        self.vector_store = vector_store

    def _token_set(self, text: str) -> set[str]:
        return set(tokenize(text))

    def _vector_scores(
        self, query_text: str, records: List[MemoryRecord]
    ) -> List[Tuple[MemoryRecord, float]]:
        query_emb = self.embedder.embed(query_text)
        return [
            (record, _cosine_similarity(query_emb, record.embedding))
            for record in records
        ]

    def _keyword_scores(
        self, query_text: str, records: List[MemoryRecord]
    ) -> List[Tuple[MemoryRecord, float]]:
        query_tokens = self._token_set(query_text)
        results: List[Tuple[MemoryRecord, float]] = []
        for record in records:
            doc_tokens = self._token_set(record.text)
            intersection = len(query_tokens & doc_tokens)
            union = len(query_tokens | doc_tokens)
            score = intersection / union if union else 0.0
            results.append((record, score))
        return results

    def retrieve(
        self,
        query_text: str,
        mode: str = "hybrid",
        top_k: int = 5,
        vector_weight: float = 0.7,
    ) -> List[Tuple[MemoryRecord, float]]:
        """Rank records for ``query_text``.

        Args:
            query_text: The query string.
            mode: ``vector``, ``keyword``, or ``hybrid``.
            top_k: Maximum number of results to return.
            vector_weight: Weight for vector score when ``mode == "hybrid"``.
                Keyword score receives ``1 - vector_weight``.
        """
        records = list(self.vector_store.records.values())
        if not records:
            return []

        if mode == "vector":
            scores = self._vector_scores(query_text, records)
        elif mode == "keyword":
            scores = self._keyword_scores(query_text, records)
        elif mode == "hybrid":
            v_scores = self._vector_scores(query_text, records)
            k_scores = self._keyword_scores(query_text, records)
            scores = []
            for (record, v_score), (_, k_score) in zip(v_scores, k_scores):
                combined = vector_weight * v_score + (1 - vector_weight) * k_score
                scores.append((record, combined))
        else:
            raise ValueError(f"Unknown retrieval mode: {mode}")

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
