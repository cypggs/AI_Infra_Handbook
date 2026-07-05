"""gang.py 测试。"""
import pytest

from gpu_scheduling_mini.gang import GangScheduler, PodGroupState
from gpu_scheduling_mini.scheduler import Scheduler
from gpu_scheduling_mini.apiserver import FakeApiServer
from gpu_scheduling_mini import model


def _make_cluster(gpu_counts):
    api = FakeApiServer()
    for name, count in gpu_counts.items():
        api.create(model.make_node(name, gpu_count=count))
    return api


def test_gang_all_or_nothing_fails_when_insufficient():
    api = _make_cluster({"n1": 1})
    scheduler = Scheduler(api)
    gang = GangScheduler(api, scheduler)

    pg = model.make_podgroup("pg", min_member=2)
    api.create(pg)
    for i in range(2):
        pod = model.make_pod(f"w{i}", pod_group_name="pg", containers=[{
            "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 1}},
        }])
        api.create(pod)

    ok, msg = gang.schedule_group(pg)
    assert not ok
    assert pg["status"]["phase"] == PodGroupState.Pending
    # 没有 Pod 被绑定
    for i in range(2):
        p = api.get("Pod", "default", f"w{i}")
        assert not p["spec"].get("nodeName")


def test_gang_succeeds_when_sufficient():
    api = _make_cluster({"n1": 2})
    scheduler = Scheduler(api)
    gang = GangScheduler(api, scheduler)

    pg = model.make_podgroup("pg", min_member=2)
    api.create(pg)
    for i in range(2):
        pod = model.make_pod(f"w{i}", pod_group_name="pg", containers=[{
            "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 1}},
        }])
        api.create(pod)

    ok, msg = gang.schedule_group(pg)
    assert ok
    assert pg["status"]["phase"] == PodGroupState.Scheduled
    for i in range(2):
        p = api.get("Pod", "default", f"w{i}")
        assert p["spec"]["nodeName"] == "n1"


def test_gang_rollback_on_midway_failure():
    api = _make_cluster({"n1": 1, "n2": 1})
    scheduler = Scheduler(api)
    gang = GangScheduler(api, scheduler)

    pg = model.make_podgroup("pg", min_member=2)
    api.create(pg)
    # 第一个 Pod 要 1 卡（n1 或 n2 均可），第二个 Pod 要 2 卡（没有节点满足）
    p0 = model.make_pod("w0", pod_group_name="pg", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 1}},
    }])
    p1 = model.make_pod("w1", pod_group_name="pg", containers=[{
        "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 2}},
    }])
    api.create(p0)
    api.create(p1)

    ok, msg = gang.schedule_group(pg)
    assert not ok
    # 第一个 Pod 即使被临时绑定，也应在回滚后释放
    assert not api.get("Pod", "default", "w0")["spec"].get("nodeName")
    # 节点资源应被完整释放
    n1 = api.get("Node", "default", "n1")
    assert model.node_free_gpus(n1) == 1


def test_schedule_all_processes_multiple_groups():
    api = _make_cluster({"n1": 4})
    scheduler = Scheduler(api)
    gang = GangScheduler(api, scheduler)

    for gid in ["g1", "g2"]:
        pg = model.make_podgroup(gid, min_member=2)
        api.create(pg)
        for i in range(2):
            pod = model.make_pod(f"{gid}-w{i}", pod_group_name=gid, containers=[{
                "name": "c", "resources": {"requests": {model.GPU_RESOURCE: 1}},
            }])
            api.create(pod)

    results = gang.schedule_all()
    assert len(results) == 2
    assert all(ok for _, ok, _ in results)
    n1 = api.get("Node", "default", "n1")
    assert model.node_free_gpus(n1) == 0
