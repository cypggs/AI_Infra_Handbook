from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.long_term_memory import LongTermMemory
from agent_memory_mini.vector_store import InMemoryVectorStore


def test_remember_and_recall_facts():
    embedder = DeterministicEmbedder(dim=64)
    ltm = LongTermMemory(InMemoryVectorStore(), embedder)

    ltm.remember("I love Python", {"topic": "preference"})
    ltm.remember("I dislike Java")

    results = ltm.recall("programming preference", top_k=2)
    assert len(results) == 2
    assert "Python" in results[0].text


def test_fact_id_increments():
    embedder = DeterministicEmbedder(dim=16)
    ltm = LongTermMemory(InMemoryVectorStore(), embedder)
    id1 = ltm.remember("a")
    id2 = ltm.remember("b")
    assert id1 == "fact-0"
    assert id2 == "fact-1"
