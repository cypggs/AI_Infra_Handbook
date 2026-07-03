"""In-memory vector store with cosine similarity and metadata filtering."""

from __future__ import annotations

import math
from dataclasses import dataclass

from rag_mini.documents import Chunk
from rag_mini.embedder import EmbeddedChunk, Embedder


@dataclass(frozen=True)
class SearchResult:
    """A single search result with its chunk and similarity score."""

    chunk: Chunk
    score: float


class VectorStore:
    """Simple in-memory vector store for dense similarity search.

    The store indexes pre-computed embedded chunks and supports cosine
    similarity search with optional metadata filtering by source or section.
    """

    def __init__(self, embedded_chunks: list[EmbeddedChunk] | None = None) -> None:
        """Initialize the store from embedded chunks.

        Args:
            embedded_chunks: Pre-computed chunks to index. If None, the store
                embeds the default Acme Corp corpus automatically.
        """
        if embedded_chunks is None:
            embedder = Embedder()
            embedded_chunks = embedder.get_embedded_chunks()
        self._items = list(embedded_chunks)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def chunks(self) -> list[Chunk]:
        """Return all stored chunks."""
        return [item.chunk for item in self._items]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _matches_metadata(self, item: EmbeddedChunk, filters: dict[str, str] | None) -> bool:
        """Return True if a chunk satisfies all metadata filters."""
        if not filters:
            return True
        for key, value in filters.items():
            if key == "source" and item.chunk.source != value:
                return False
            if key == "section" and item.chunk.section != value:
                return False
        return True

    def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        """Find the top-k chunks most similar to the query vector.

        Args:
            query_vector: Dense query embedding.
            top_k: Number of results to return.
            filters: Optional metadata filters, e.g. {"source": "support-policy"}.

        Returns:
            Top-k search results sorted by cosine similarity, highest first.
        """
        scored: list[tuple[float, EmbeddedChunk]] = []
        for item in self._items:
            if not self._matches_metadata(item, filters):
                continue
            score = self._cosine_similarity(query_vector, item.vector)
            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            SearchResult(chunk=item.chunk, score=score)
            for score, item in scored[:top_k]
        ]
