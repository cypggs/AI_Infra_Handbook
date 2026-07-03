"""Tests for the in-memory vector store."""

from rag_mini.documents import load_chunks
from rag_mini.embedder import Embedder
from rag_mini.vector_store import VectorStore


def test_vector_store_size():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    assert len(store) == len(chunks)


def test_similarity_search_returns_results():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    query_vector = embedder.embed_query("return policy")
    results = store.similarity_search(query_vector, top_k=2)
    assert len(results) == 2
    assert all(0.0 <= r.score <= 1.0 for r in results)


def test_similarity_search_sorted():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    query_vector = embedder.embed_query("warranty")
    results = store.similarity_search(query_vector, top_k=3)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_metadata_filter_source():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    query_vector = embedder.embed_query("return policy")
    results = store.similarity_search(
        query_vector, top_k=10, filters={"source": "support-policy"}
    )
    assert len(results) > 0
    assert all(r.chunk.source == "support-policy" for r in results)


def test_metadata_filter_section():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    query_vector = embedder.embed_query("return policy")
    results = store.similarity_search(
        query_vector, top_k=10, filters={"section": "returns"}
    )
    assert len(results) > 0
    assert all(r.chunk.section == "returns" for r in results)


def test_similarity_search_no_matches_with_filter():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    store = VectorStore(embedder.get_embedded_chunks())
    query_vector = embedder.embed_query("return policy")
    results = store.similarity_search(
        query_vector, top_k=10, filters={"section": "nonexistent"}
    )
    assert results == []


def test_vector_store_default_corpus():
    store = VectorStore()
    assert len(store) > 0
