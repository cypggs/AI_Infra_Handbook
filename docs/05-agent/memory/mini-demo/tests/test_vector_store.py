from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.vector_store import InMemoryVectorStore


def test_add_search_ranking_and_delete():
    embedder = DeterministicEmbedder(dim=64)
    store = InMemoryVectorStore()

    store.add("1", "Python is great", embedder.embed("Python is great"))
    store.add("2", "Java is verbose", embedder.embed("Java is verbose"))
    store.add("3", "Python vs Java", embedder.embed("Python vs Java"))

    results = store.search(embedder.embed("Python language"), top_k=2)
    assert len(results) == 2
    assert results[0].id == "1"
    assert all(r.score is not None for r in results)

    assert store.delete("2") is True
    assert store.delete("2") is False
    assert len(store.records) == 2
    assert store.get("2") is None
