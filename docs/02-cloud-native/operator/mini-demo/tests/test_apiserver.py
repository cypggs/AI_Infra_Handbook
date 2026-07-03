"""apiserver 语义测试：乐观并发、generation、/status 子资源、finalizer、级联 GC。"""
import pytest
from operator_mini import model
from operator_mini.apiserver import FakeApiServer, Conflict, NotFound


def test_create_assigns_resourceversion():
    api = FakeApiServer()
    obj = api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    assert obj["metadata"]["resourceVersion"] != "0"
    assert obj["metadata"]["generation"] == 1


def test_optimistic_lock_stale_rv_conflicts():
    api = FakeApiServer()
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    v1 = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    # 模拟另一个写者先改了
    v2 = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    v2["spec"]["replicas"] = 2
    api.update(v2)
    # v1 现在带着过期 rv → 冲突
    v1["spec"]["replicas"] = 3
    with pytest.raises(Conflict):
        api.update(v1)


def test_generation_bumps_on_spec_not_status():
    api = FakeApiServer()
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    obj = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    assert obj["metadata"]["generation"] == 1

    # spec 变 → generation +1
    obj["spec"]["replicas"] = 2
    obj = api.update(obj)
    assert obj["metadata"]["generation"] == 2

    # status 变 → generation 不变
    obj["status"]["ready"] = True
    obj = api.update_status(obj)
    assert obj["metadata"]["generation"] == 2


def test_status_subresource_independent_rv():
    api = FakeApiServer()
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    obj = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    obj["status"] = {"readyReplicas": 1}
    updated = api.update_status(obj)
    assert updated["status"]["readyReplicas"] == 1


def test_delete_with_finalizer_only_sets_timestamp():
    api = FakeApiServer()
    obj = api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    model.add_finalizer(obj)
    api.update(obj)

    api.delete(model.INFERENCE_SERVICE_KIND, "default", "a")
    still_there = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    assert still_there is not None, "有 finalizer 不应真删"
    assert still_there["metadata"]["deletionTimestamp"] is not None


def test_removing_finalizer_finalizes():
    api = FakeApiServer()
    obj = api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    model.add_finalizer(obj)
    api.update(obj)
    api.delete(model.INFERENCE_SERVICE_KIND, "default", "a")

    cur = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    model.remove_finalizer(cur)
    api.update(cur)   # 删除中 + 无 finalizer → 真删
    assert api.get(model.INFERENCE_SERVICE_KIND, "default", "a") is None


def test_cascade_gc_children():
    api = FakeApiServer()
    parent = api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    dep = model.make_deployment("a", image="img", replicas=1, labels={})
    model.set_owner_reference(dep, parent)
    api.create(dep)
    svc = model.make_service("a", port=80, selector={}, labels={})
    model.set_owner_reference(svc, parent)
    api.create(svc)

    api.delete(model.INFERENCE_SERVICE_KIND, "default", "a")  # 无 finalizer → 直接删 + GC
    assert api.get(model.INFERENCE_SERVICE_KIND, "default", "a") is None
    assert api.get(model.DEPLOYMENT_KIND, "default", "a") is None, "子 Deployment 应被级联回收"
    assert api.get(model.SERVICE_KIND, "default", "a") is None, "子 Service 应被级联回收"


def test_events_stream():
    api = FakeApiServer()
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    types = [e["type"] for e in api.events_since(0)]
    assert types == ["ADDED"]


def test_inject_conflict_hook():
    api = FakeApiServer()
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    obj = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    obj["spec"]["replicas"] = 2
    api.inject_conflict(1)
    with pytest.raises(Conflict):
        api.update(obj)
    # 注入用尽后可正常写
    obj2 = api.get(model.INFERENCE_SERVICE_KIND, "default", "a")
    obj2["spec"]["replicas"] = 2
    api.update(obj2)


def test_not_found():
    api = FakeApiServer()
    with pytest.raises(NotFound):
        api.update(model.make_inference_service("ghost", image="img", replicas=1, model="m"))
