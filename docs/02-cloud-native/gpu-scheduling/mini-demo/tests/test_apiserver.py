"""apiserver.py 测试。"""
import pytest

from gpu_scheduling_mini.apiserver import FakeApiServer, Conflict, NotFound
from gpu_scheduling_mini import model


def _node(name):
    return model.make_node(name, gpu_count=1)


def test_create_and_get():
    api = FakeApiServer()
    node = _node("n1")
    created = api.create(node)
    assert created["metadata"]["resourceVersion"] == "1"
    assert api.get("Node", "default", "n1")["metadata"]["name"] == "n1"


def test_create_conflict():
    api = FakeApiServer()
    api.create(_node("n1"))
    with pytest.raises(Conflict):
        api.create(_node("n1"))


def test_update_optimistic_lock():
    api = FakeApiServer()
    n = api.create(_node("n1"))
    n["metadata"]["resourceVersion"] = "0"  # 故意写错 rv
    with pytest.raises(Conflict):
        api.update(n)


def test_generation_only_bumps_on_spec_change():
    api = FakeApiServer()
    n = api.create(_node("n1"))
    gen_before = n["metadata"]["generation"]
    n["status"]["phase"] = "Ready"
    updated = api.update(n)
    assert updated["metadata"]["generation"] == gen_before


def test_update_status_does_not_bump_generation():
    api = FakeApiServer()
    n = api.create(_node("n1"))
    gen = n["metadata"]["generation"]
    n["status"]["phase"] = "Ready"
    updated = api.update_status(n)
    assert updated["metadata"]["generation"] == gen
    assert updated["status"]["phase"] == "Ready"


def test_events_stream():
    api = FakeApiServer()
    api.create(_node("n1"))
    idx = api.event_index()
    n = api.get("Node", "default", "n1")
    n["status"]["phase"] = "Ready"
    api.update_status(n)
    events = api.events_since(idx)
    assert len(events) == 1
    assert events[0]["type"] == "MODIFIED"


def test_delete_emits_deleted_event():
    api = FakeApiServer()
    api.create(_node("n1"))
    idx = api.event_index()
    api.delete("Node", "default", "n1")
    events = api.events_since(idx)
    assert events[0]["type"] == "DELETED"
    assert api.get("Node", "default", "n1") is None
