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


def test_update_fact_supersedes_old_record():
    embedder = DeterministicEmbedder(dim=64)
    ltm = LongTermMemory(InMemoryVectorStore(), embedder)

    old_id = ltm.remember("Alice 住在北京")
    new_id = ltm.update_fact(old_id, "Alice 住在上海")

    old = ltm.store.get(old_id)
    assert old.metadata["lifecycle_state"] == "superseded"
    assert old.metadata["replaced_by"] == new_id
    assert "valid_until" in old.metadata

    # 旧事实仍在库中（审计/时序查询可用），但 latest_only 会隐藏它
    assert len(ltm.recall("Alice 住在", top_k=10)) == 2
    latest = ltm.recall("Alice 住在", top_k=10, latest_only=True)
    assert len(latest) == 1
    assert "上海" in latest[0].text

    # 新记录是 active，并指回被取代的记录
    new = ltm.store.get(new_id)
    assert new.metadata["lifecycle_state"] == "active"
    assert new.metadata["supersedes"] == old_id


def test_consolidate_merges_exact_duplicates():
    embedder = DeterministicEmbedder(dim=64)
    ltm = LongTermMemory(InMemoryVectorStore(), embedder)

    ltm.remember("用户喜欢简洁的 Markdown 周报")
    dup_id = ltm.remember("用户喜欢简洁的 Markdown 周报")
    ltm.remember("项目 Phoenix 使用 Python 3.11")

    merged = ltm.consolidate()
    assert merged == [dup_id]
    dup = ltm.store.get(dup_id)
    assert dup.metadata["lifecycle_state"] == "merged"
    assert dup.metadata["merged_into"] == "fact-0"

    # 合并不删数据：全量检索仍在，latest_only 隐藏 merged 记录
    assert len(ltm.recall("Markdown 周报", top_k=10)) == 3
    assert len(ltm.recall("Markdown 周报", top_k=10, latest_only=True)) == 2


def test_update_unknown_id_raises():
    embedder = DeterministicEmbedder(dim=16)
    ltm = LongTermMemory(InMemoryVectorStore(), embedder)
    try:
        ltm.update_fact("fact-404", "whatever")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")
