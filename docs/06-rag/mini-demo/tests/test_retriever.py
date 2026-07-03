"""Tests for dense, keyword, and hybrid retrieval."""

from rag_mini.documents import load_chunks
from rag_mini.embedder import Embedder
from rag_mini.retriever import Retriever
from rag_mini.vector_store import VectorStore


def _make_retriever():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    return Retriever(embedder=embedder, vector_store=store)


def test_dense_search_returns_top_k():
    retriever = _make_retriever()
    results = retriever.dense_search("return policy", top_k=3)
    assert len(results) == 3
    assert all(r.dense_score >= 0.0 for r in results)
    assert results[0].dense_score >= results[-1].dense_score


def test_keyword_search_returns_top_k():
    retriever = _make_retriever()
    results = retriever.keyword_search("return policy", top_k=3)
    assert len(results) > 0
    assert all(r.keyword_score > 0.0 for r in results)
    assert results[0].keyword_score >= results[-1].keyword_score


def test_hybrid_search_returns_top_k():
    retriever = _make_retriever()
    results = retriever.hybrid_search("return policy", top_k=3)
    assert len(results) == 3
    assert all(r.rrf_score > 0.0 for r in results)
    assert results[0].rrf_score >= results[-1].rrf_score


def test_hybrid_includes_returns_section():
    retriever = _make_retriever()
    results = retriever.hybrid_search("return policy", top_k=3)
    sections = {r.chunk.section for r in results}
    assert "returns" in sections


def test_dense_search_with_metadata_filter():
    retriever = _make_retriever()
    results = retriever.dense_search("return policy", top_k=10, filters={"section": "returns"})
    assert len(results) > 0
    assert all(r.chunk.section == "returns" for r in results)


def test_keyword_search_empty_query():
    retriever = _make_retriever()
    results = retriever.keyword_search("", top_k=3)
    assert results == []


def test_hybrid_search_rank_consistency():
    retriever = _make_retriever()
    results1 = retriever.hybrid_search("return policy", top_k=3)
    results2 = retriever.hybrid_search("return policy", top_k=3)
    assert [r.chunk.id for r in results1] == [r.chunk.id for r in results2]
