"""scheduler.py 测试。"""
import pytest

from gpu_scheduling_mini.scheduler import Scheduler
from gpu_scheduling_mini.apiserver import FakeApiServer
from gpu_scheduling_mini import model
from gpu_scheduling_mini.topology import Topology, TopologyScorer


def test_filter_excludes_insufficient_node():
    api = FakeApiServer()
    api.create(model.make_node("n2", gpu_count=1))
    scheduler = Scheduler(api)
    pod = model.make_pod("p", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 2}},
    }])
    api.create(pod)
    assert scheduler.find_best_node(pod) is None


def test_schedule_one_binds_to_best_node():
    api = FakeApiServer()
    api.create(model.make_node("n2", gpu_count=2))
    api.create(model.make_node("n4", gpu_count=4))
    scheduler = Scheduler(api)
    pod = model.make_pod("p", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 2}},
    }])
    api.create(pod)
    assert scheduler.schedule_one(pod)
    assert pod["spec"]["nodeName"] in ("n2", "n4")
    assert len(pod["status"]["allocated_devices"][model.GPU_RESOURCE]) == 2
    # 节点资源确实被扣减
    bound = api.get("Node", "default", pod["spec"]["nodeName"])
    assert model.node_free_gpus(bound) == bound["status"]["capacity"][model.GPU_RESOURCE] - 2


def test_scheduler_respects_pod_nodename():
    api = FakeApiServer()
    api.create(model.make_node("n2", gpu_count=2))
    api.create(model.make_node("n4", gpu_count=4))
    scheduler = Scheduler(api)
    pod = model.make_pod("p", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 1}},
    }])
    pod["spec"]["nodeName"] = "n2"
    api.create(pod)
    scheduler.schedule_one(pod)
    assert pod["spec"]["nodeName"] == "n2"


def test_mig_scheduling():
    api = FakeApiServer()
    api.create(model.make_node("mig", gpu_count=0, mig_devices={"1g.5gb": 4}))
    scheduler = Scheduler(api)
    pod = model.make_pod("p", containers=[{
        "name": "c", "resources": {"requests": {f"{model.MIG_RESOURCE_PREFIX}1g.5gb": 2}},
    }])
    api.create(pod)
    assert scheduler.schedule_one(pod)
    assert pod["spec"]["nodeName"] == "mig"
    assert len(pod["status"]["allocated_devices"][f"{model.MIG_RESOURCE_PREFIX}1g.5gb"]) == 2


def test_shared_gpu_scheduling():
    api = FakeApiServer()
    api.create(model.make_node("shared", gpu_count=1))
    scheduler = Scheduler(api)
    pod = model.make_pod("p", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_SHARED_RESOURCE: 5}},
    }])
    api.create(pod)
    assert scheduler.schedule_one(pod)
    assert pod["status"]["allocated_devices"][model.GPU_SHARED_RESOURCE] == 5


def test_shared_gpu_capacity_enforced():
    api = FakeApiServer()
    api.create(model.make_node("shared", gpu_count=1))
    scheduler = Scheduler(api)
    pod = model.make_pod("p", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_SHARED_RESOURCE: 11}},
    }])
    api.create(pod)
    assert not scheduler.schedule_one(pod)
