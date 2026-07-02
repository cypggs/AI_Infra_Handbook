import pytest

from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.retriever import MemoryRetriever
from agent_memory_mini.vector_store import InMemoryVectorStore


@pytest.fixture
def retriever():
    embedder = DeterministicEmbedder(dim=64)
    store = InMemoryVectorStore()
    facts = [
        ("f1", "Python is a popular programming language"),
        ("f2", "Java is used in enterprise backends"),
        ("f3", "Cats are small mammals"),
    ]
    for fid, text in facts:
        store.add(fid, text, embedder.embed(text))
    return MemoryRetriever(embedder, store)


def test_vector_retrieval(retriever):
    results = retriever.retrieve(
        "programming language", mode="vector", top_k=2
    )
    assert len(results) == 2
    ids = [r[0].id for r in results]
    assert "f1" in ids


def test_keyword_retrieval(retriever):
    results = retriever.retrieve(
        "Python programming", mode="keyword", top_k=2
    )
    ids = [r[0].id for r in results]
    assert "f1" in ids


def test_hybrid_retrieval(retriever):
    results = retriever.retrieve(
        "programming language", mode="hybrid", top_k=3
    )
    ids = [r[0].id for r in results]
    assert ids[0] == "f1"


def test_unknown_mode_raises(retriever):
    with pytest.raises(ValueError):
        retriever.retrieve("query", mode="invalid")
