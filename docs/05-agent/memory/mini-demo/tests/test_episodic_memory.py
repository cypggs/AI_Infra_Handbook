from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.episodic_memory import EpisodicMemory
from agent_memory_mini.vector_store import InMemoryVectorStore


def test_store_and_recall_episodes():
    embedder = DeterministicEmbedder(dim=64)
    em = EpisodicMemory(InMemoryVectorStore(), embedder)

    em.store("solve math problem", ["calculator"], "success")
    em.store("write a poem", ["draft", "revise"], "success")

    results = em.recall("math task", top_k=2)
    assert len(results) >= 1
    assert "solve math problem" in results[0].text


def test_episode_contains_actions_and_outcome():
    embedder = DeterministicEmbedder(dim=32)
    em = EpisodicMemory(InMemoryVectorStore(), embedder)
    eid = em.store("goal", ["action1", "action2"], "ok")
    record = em.vector_store.get(eid)
    assert "action1" in record.text
    assert "Outcome: ok" in record.text
