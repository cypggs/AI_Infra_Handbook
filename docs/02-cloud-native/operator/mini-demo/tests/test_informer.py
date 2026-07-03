"""Informer 测试：List 基线、Watch 增量、缓存更新、EventHandler 回调。"""
from operator_mini import model
from operator_mini.apiserver import FakeApiServer
from operator_mini.informer import Informer, enqueue_self, enqueue_owner
from operator_mini.workqueue import RateLimitingQueue, FakeClock


def test_full_sync_loads_existing():
    api = FakeApiServer()
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    q = RateLimitingQueue(FakeClock())
    inf = Informer(api, model.INFERENCE_SERVICE_KIND, enqueue_self(q))
    assert inf.get(model.INFERENCE_SERVICE_KIND, "default", "a") is not None


def test_pump_picks_up_new_events():
    api = FakeApiServer()
    events = []
    inf = Informer(api, model.INFERENCE_SERVICE_KIND, lambda t, o: events.append((t, o["metadata"]["name"])))
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    n = inf.pump()
    assert n == 1
    assert inf.get(model.INFERENCE_SERVICE_KIND, "default", "a") is not None
    assert events == [("ADDED", "a")]


def test_deleted_removed_from_cache():
    api = FakeApiServer()
    inf = Informer(api, model.INFERENCE_SERVICE_KIND, lambda t, o: None)
    api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    inf.pump()
    api.delete(model.INFERENCE_SERVICE_KIND, "default", "a")
    inf.pump()
    assert inf.get(model.INFERENCE_SERVICE_KIND, "default", "a") is None


def test_enqueue_owner_maps_child_to_parent():
    api = FakeApiServer()
    parent = api.create(model.make_inference_service("a", image="img", replicas=1, model="m"))
    q = RateLimitingQueue(FakeClock())
    inf = Informer(api, model.DEPLOYMENT_KIND, enqueue_owner(q, model.INFERENCE_SERVICE_KIND))
    dep = model.make_deployment("a", image="img", replicas=1, labels={})
    model.set_owner_reference(dep, parent)
    api.create(dep)
    inf.pump()
    assert q.depth() == 1
    assert q.get() == (model.INFERENCE_SERVICE_KIND, "default", "a")


def test_enqueue_self_dedupes():
    q = RateLimitingQueue(FakeClock())
    # 同一个 key 连续入队多次，只应保留一个（level-triggered 抗事件风暴的基础）
    k = (model.INFERENCE_SERVICE_KIND, "default", "a")
    q.add(k)
    q.add(k)
    q.add(k)
    assert q.depth() == 1
