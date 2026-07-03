"""Tests for the simple score-based reranker."""

from rag_mini.documents import Chunk
from rag_mini.embedder import Embedder
from rag_mini.retriever import Retriever
from rag_mini.reranker import Reranker


def test_reranker_sorts_results():
    embedder = Embedder()
    retriever = Retriever(embedder=embedder)
    candidates = retriever.hybrid_search("return policy", top_k=3)
    reranker = Reranker()
    ranked = reranker.rerank("return policy", candidates)
    assert len(ranked) == len(candidates)
    scores = [r.final_score for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_reranker_scores_in_range():
    embedder = Embedder()
    retriever = Retriever(embedder=embedder)
    candidates = retriever.hybrid_search("return policy", top_k=3)
    reranker = Reranker()
    ranked = reranker.rerank("return policy", candidates)
    for r in ranked:
        assert 0.0 <= r.final_score <= 1.0
        assert 0.0 <= r.overlap_score <= 1.0


def test_reranker_empty_results():
    reranker = Reranker()
    assert reranker.rerank("return policy", []) == []


def test_reranker_determinism():
    embedder = Embedder()
    retriever = Retriever(embedder=embedder)
    candidates = retriever.hybrid_search("return policy", top_k=3)
    reranker = Reranker()
    ranked1 = reranker.rerank("return policy", candidates)
    ranked2 = reranker.rerank("return policy", candidates)
    assert [r.chunk.id for r in ranked1] == [r.chunk.id for r in ranked2]
    assert [r.final_score for r in ranked1] == [r.final_score for r in ranked2]


def test_reranker_chunk_reference():
    embedder = Embedder()
    retriever = Retriever(embedder=embedder)
    candidates = retriever.hybrid_search("return policy", top_k=3)
    reranker = Reranker()
    ranked = reranker.rerank("return policy", candidates)
    assert all(isinstance(r.chunk, Chunk) for r in ranked)
