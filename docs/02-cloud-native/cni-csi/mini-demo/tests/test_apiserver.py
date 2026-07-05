"""apiserver 语义测试：resourceVersion、generation、/status、watch 事件流。"""
import pytest

from cni_csi_mini import model
from cni_csi_mini.apiserver import FakeApiServer, Conflict, NotFound


def test_create_assigns_resourceversion_and_generation():
    api = FakeApiServer()
    pod = api.create(model.make_pod("p1", node_name="node-1"))
    assert pod["metadata"]["resourceVersion"] != "0"
    assert pod["metadata"]["generation"] == 1


def test_optimistic_lock_stale_rv_conflicts():
    api = FakeApiServer()
    api.create(model.make_pod("p1", node_name="node-1"))
    v1 = api.get("Pod", "default", "p1")
    v2 = api.get("Pod", "default", "p1")
    v2["spec"]["nodeName"] = "node-2"
    api.update(v2)
    v1["spec"]["nodeName"] = "node-3"
    with pytest.raises(Conflict):
        api.update(v1)


def test_generation_bumps_on_spec_not_status():
    api = FakeApiServer()
    api.create(model.make_pod("p1"))
    obj = api.get("Pod", "default", "p1")
    obj["spec"]["nodeName"] = "node-1"
    obj = api.update(obj)
    assert obj["metadata"]["generation"] == 2

    obj["status"]["phase"] = "Running"
    obj = api.update_status(obj)
    assert obj["metadata"]["generation"] == 2


def test_status_subresource_independent_rv():
    api = FakeApiServer()
    api.create(model.make_pod("p1"))
    obj = api.get("Pod", "default", "p1")
    obj["status"]["podIP"] = "10.0.0.1"
    updated = api.update_status(obj)
    assert updated["status"]["podIP"] == "10.0.0.1"


def test_delete_emits_deleted_event():
    api = FakeApiServer()
    api.create(model.make_pod("p1"))
    api.delete("Pod", "default", "p1")
    assert api.get("Pod", "default", "p1") is None
    types = [e["type"] for e in api.events_since(0)]
    assert types == ["ADDED", "DELETED"]


def test_events_since_index():
    api = FakeApiServer()
    api.create(model.make_pod("p1"))
    idx = api.event_index()
    api.create(model.make_pod("p2"))
    events = api.events_since(idx)
    assert len(events) == 1
    assert events[0]["type"] == "ADDED"


def test_inject_conflict_hook():
    api = FakeApiServer()
    api.create(model.make_pod("p1"))
    obj = api.get("Pod", "default", "p1")
    obj["spec"]["nodeName"] = "node-1"
    api.inject_conflict(1)
    with pytest.raises(Conflict):
        api.update(obj)
    obj2 = api.get("Pod", "default", "p1")
    obj2["spec"]["nodeName"] = "node-1"
    api.update(obj2)


def test_update_not_found():
    api = FakeApiServer()
    with pytest.raises(NotFound):
        api.update(model.make_pod("ghost"))
