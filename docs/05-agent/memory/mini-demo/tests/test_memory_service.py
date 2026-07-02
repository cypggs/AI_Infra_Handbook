import json
import os
import tempfile

from agent_memory_mini.memory_service import MemoryService


def test_multi_session_recall():
    service = MemoryService()
    service.remember(
        "fact", "我喜欢 Python，不喜欢 Java", {"session": "A"}
    )
    service.remember(
        "session",
        {
            "session_id": "A",
            "messages": [
                {"role": "user", "content": "我喜欢 Python，不喜欢 Java"}
            ],
        },
    )

    results = service.recall(
        "推荐一门编程语言", memory_type="fact", top_k=1
    )
    assert len(results) == 1
    assert "Python" in results[0]["text"]
    assert results[0]["memory_type"] == "fact"


def test_remember_task_and_example():
    service = MemoryService()
    eid = service.remember(
        "task",
        {
            "goal": "recommend language",
            "actions": ["recall preference"],
            "outcome": "accepted",
        },
    )
    pid = service.remember("example", {"description": "language recommendation pattern"})
    assert eid.startswith("ep-")
    assert pid.startswith("proc-")


def test_forget_memory_and_session():
    service = MemoryService()
    fid = service.remember("fact", "Python is great")
    service.remember(
        "session",
        {"session_id": "s1", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert service.forget(fid) is True
    assert service.forget("s1") is True
    assert service.forget("missing") is False


def test_save_and_load_json():
    service = MemoryService()
    service.remember("fact", "Python is great")
    service.remember("fact", "Java is verbose")
    service.remember(
        "task",
        {"goal": "recommend language", "actions": [], "outcome": "ok"},
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "memory.json")
        service.save(path)
        data = json.load(open(path, encoding="utf-8"))
        assert "long_term" in data
        assert "episodic" in data
        assert "short_term" in data

        service2 = MemoryService()
        service2.load(path)
        facts = service2.recall("Python language", memory_type="fact", top_k=2)
        assert any("Python" in f["text"] for f in facts)


def test_consolidate_moves_working_to_short_term():
    service = MemoryService()
    service.working.add_message("user", "question one")
    service.working.add_message("assistant", "answer one")
    service.working.add_message("user", "question two")
    service.working.add_message("assistant", "answer two")

    summary = service.consolidate()
    assert service.working.get_messages() == []
    assert "Summary:" in service.short_term.get_context()
    assert summary in service.short_term.get_context()
