"""Retrieval strategies: dense, keyword (BM25-like), and hybrid with RRF."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from rag_mini.documents import Chunk
from rag_mini.embedder import EmbeddedChunk, Embedder
from rag_mini.vector_store import VectorStore


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieval result with chunk, dense score, keyword score, and RRF score."""

    chunk: Chunk
    dense_score: float
    keyword_score: float
    rrf_score: float


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


class Retriever:
    """Retriever supporting dense, keyword, and hybrid search with RRF."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._embedder = embedder if embedder is not None else Embedder()
        if vector_store is not None:
            self._store = vector_store
        else:
            self._store = VectorStore(self._embedder.get_embedded_chunks())

        self._embedded = self._embedder.get_embedded_chunks()
        self._avg_doc_length = self._compute_avg_doc_length()

    def _compute_avg_doc_length(self) -> float:
        if not self._embedded:
            return 0.0
        return sum(item.token_count for item in self._embedded) / len(self._embedded)

    def _bm25_keyword_scores(
        self,
        query: str,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> dict[str, float]:
        """Compute BM25-like keyword scores for the query against all chunks."""
        tokens = _tokenize(query)
        if not tokens or not self._embedded:
            return {}

        unique_terms = set(tokens)
        num_docs = len(self._embedded)

        doc_freq: dict[str, int] = {term: 0 for term in unique_terms}
        for item in self._embedded:
            item_terms = set(item.term_freq.keys())
            for term in unique_terms:
                if term in item_terms:
                    doc_freq[term] += 1

        scores: dict[str, float] = {}
        for item in self._embedded:
            score = 0.0
            doc_len = item.token_count
            for term in unique_terms:
                tf = item.term_freq.get(term, 0)
                if tf == 0:
                    continue
                df = doc_freq[term]
                idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1)
                denom = tf + k1 * (1 - b + b * doc_len / self._avg_doc_length)
                score += idf * (tf * (k1 + 1) / denom)
            if score > 0:
                scores[item.chunk.id] = score

        return scores

    def dense_search(
        self,
        query: str,
        top_k: int = 3,
        filters: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve top-k chunks using dense cosine similarity."""
        query_vector = self._embedder.embed_query(query)
        results = self._store.similarity_search(
            query_vector, top_k=top_k, filters=filters
        )
        return [
            RetrievalResult(
                chunk=r.chunk,
                dense_score=r.score,
                keyword_score=0.0,
                rrf_score=0.0,
            )
            for r in results
        ]

    def keyword_search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """Retrieve top-k chunks using BM25-like keyword scores."""
        scores = self._bm25_keyword_scores(query)
        sorted_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
        id_to_chunk = {item.chunk.id: item.chunk for item in self._embedded}
        return [
            RetrievalResult(
                chunk=id_to_chunk[chunk_id],
                dense_score=0.0,
                keyword_score=scores[chunk_id],
                rrf_score=0.0,
            )
            for chunk_id in sorted_ids
        ]

    def hybrid_search(
        self,
        query: str,
        top_k: int = 3,
        filters: dict[str, str] | None = None,
        rrf_k: int = 60,
    ) -> list[RetrievalResult]:
        """Retrieve top-k chunks by fusing dense and keyword rankings with RRF."""
        dense_results = self.dense_search(query, top_k=top_k * 2, filters=filters)
        keyword_results = self.keyword_search(query, top_k=top_k * 2)

        rrf_scores: dict[str, float] = {}
        dense_map: dict[str, RetrievalResult] = {}
        keyword_map: dict[str, RetrievalResult] = {}

        for rank, result in enumerate(dense_results, start=1):
            chunk_id = result.chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (rank + rrf_k)
            dense_map[chunk_id] = result

        for rank, result in enumerate(keyword_results, start=1):
            chunk_id = result.chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (rank + rrf_k)
            keyword_map[chunk_id] = result

        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
        fused: list[RetrievalResult] = []
        for chunk_id in sorted_ids:
            dense_score = dense_map[chunk_id].dense_score if chunk_id in dense_map else 0.0
            keyword_score = (
                keyword_map[chunk_id].keyword_score if chunk_id in keyword_map else 0.0
            )
            chunk = (
                dense_map[chunk_id].chunk
                if chunk_id in dense_map
                else keyword_map[chunk_id].chunk
            )
            fused.append(
                RetrievalResult(
                    chunk=chunk,
                    dense_score=dense_score,
                    keyword_score=keyword_score,
                    rrf_score=rrf_scores[chunk_id],
                )
            )

        return fused
