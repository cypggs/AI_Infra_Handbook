"""test_store.py — etcd 模拟（强一致 KV + watch/notify）单元测试。

覆盖：
  - put 首次 ADDED，再次 MODIFIED
  - get / delete / all_of
  - watcher 收到事件
"""

from k8s_mini.store import Event, EventType, Store


def test_put_then_get_roundtrip():
    s = Store()
    s.put("pod", "p1", {"name": "p1"})
    got = s.get("pod", "p1")
    assert got == {"name": "p1"}


def test_put_emits_added_then_modified():
    events = []
    s = Store()
    s.add_watcher(lambda e: events.append(e))
    s.put("pod", "p1", {"v": 1})   # ADDED
    s.put("pod", "p1", {"v": 2})   # MODIFIED
    assert [e.type for e in events] == [EventType.ADDED, EventType.MODIFIED]


def test_delete_emits_deleted_and_removes():
    events = []
    s = Store()
    s.add_watcher(lambda e: events.append(e))
    s.put("pod", "p1", {"v": 1})
    s.delete("pod", "p1")
    assert events[-1].type == EventType.DELETED
    assert s.get("pod", "p1") is None


def test_delete_missing_returns_none():
    s = Store()
    assert s.delete("pod", "nope") is None


def test_all_of_filters_by_kind():
    s = Store()
    s.put("pod", "p1", {"name": "p1"})
    s.put("node", "n1", {"name": "n1"})
    s.put("pod", "p2", {"name": "p2"})
    pods = s.all_of("pod")
    assert {p["name"] for p in pods} == {"p1", "p2"}
    assert len(s.all_of("node")) == 1
    assert s.all_of("deployment") == []


def test_watcher_exception_does_not_break_store():
    s = Store()
    s.add_watcher(lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
    s.add_watcher(lambda e: setattr(s, "_seen", e.type))
    s.put("pod", "p1", {"v": 1})
    # 第二个 watcher 仍被调用（store 容错）
    assert s._seen == EventType.ADDED
