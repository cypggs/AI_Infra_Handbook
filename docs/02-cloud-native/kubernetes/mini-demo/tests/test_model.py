"""test_model.py — 资源/节点/Pod 数据模型单元测试。

覆盖：
  - Resources.fits / add / sub（sub 不足时抛错）
  - Node.allocate / release / allocatable
  - Pod.total_request = 各容器 requests 之和
  - ReplicaSet.matches（标签选择器）
  - Pod.scheduled / Pod.is_gang
"""

import pytest

from k8s_mini.model import (
    Condition,
    Container,
    Deployment,
    Node,
    Pod,
    PodPhase,
    ReplicaSet,
    Resources,
    Taint,
    Toleration,
)


# ----------------------------- Resources -----------------------------

def test_resources_defaults_zero():
    r = Resources()
    assert (r.cpu, r.memory, r.gpu) == (0, 0, 0)


def test_resources_fits_true_when_enough():
    node_free = Resources(cpu=4000, memory=8000, gpu=2)
    req = Resources(cpu=1000, memory=1000, gpu=1)
    assert node_free.fits(req)


def test_resources_fits_false_when_gpu_short():
    node_free = Resources(cpu=4000, memory=8000, gpu=0)
    req = Resources(cpu=1000, memory=1000, gpu=1)
    assert not node_free.fits(req)


def test_resources_add_and_sub_roundtrip():
    a = Resources(1000, 1024, 1)
    b = Resources(2000, 2048, 1)
    s = a.add(b)
    assert (s.cpu, s.memory, s.gpu) == (3000, 3072, 2)
    back = s.sub(b)
    assert back == a


def test_resources_sub_raises_when_insufficient():
    big = Resources(4000, 8000, 0)
    too_much = Resources(5000, 8000, 0)
    with pytest.raises(ValueError):
        big.sub(too_much)


# ----------------------------- Node -----------------------------

def test_node_allocatable_starts_full():
    n = Node(name="n1", capacity=Resources(4000, 8000, 0))
    a = n.allocatable
    assert (a.cpu, a.memory, a.gpu) == (4000, 8000, 0)


def test_node_allocate_decreases_allocatable():
    n = Node(name="n1", capacity=Resources(4000, 8000, 0))
    n.allocate(Resources(1000, 1000, 0))
    a = n.allocatable
    assert (a.cpu, a.memory) == (3000, 7000)


def test_node_release_restores_allocatable():
    n = Node(name="n1", capacity=Resources(4000, 8000, 0))
    n.allocate(Resources(1000, 1000, 0))
    n.release(Resources(1000, 1000, 0))
    assert n.allocatable == Resources(4000, 8000, 0)


# ----------------------------- Pod -----------------------------

def test_pod_total_request_sums_containers():
    pod = Pod(
        name="multi",
        containers=[
            Container(name="a", requests=Resources(1000, 1024, 0)),
            Container(name="b", requests=Resources(2000, 2048, 1)),
        ],
    )
    total = pod.total_request
    assert (total.cpu, total.memory, total.gpu) == (3000, 3072, 1)


def test_pod_single_container_total_request():
    pod = Pod(
        name="single",
        containers=[Container(name="a", requests=Resources(500, 512, 1))],
    )
    assert (pod.total_request.cpu, pod.total_request.gpu) == (500, 1)


def test_pod_scheduled_flag_tracks_condition():
    pod = Pod(name="p", containers=[Container(name="a")])
    assert not pod.scheduled
    pod.conditions.add(Condition.POD_SCHEDULED)
    assert pod.scheduled


def test_pod_is_gang_flag():
    plain = Pod(name="p", containers=[Container(name="a")])
    gang = Pod(name="g", containers=[Container(name="a")], gang_id="g1")
    assert not plain.is_gang
    assert gang.is_gang


# ----------------------------- ReplicaSet / Deployment -----------------------------

def test_replicaset_matches_by_label():
    tpl = Pod(name="t", containers=[Container(name="a")])
    rs = ReplicaSet(name="rs", replicas=3, template_labels={"app": "web"}, pod_template=tpl)
    match = Pod(name="m", containers=[Container(name="a")], labels={"app": "web"})
    nomatch = Pod(name="n", containers=[Container(name="a")], labels={"app": "api"})
    assert rs.matches(match)
    assert not rs.matches(nomatch)


def test_deployment_default_rolling_params():
    dep = Deployment(
        name="web",
        replicas=3,
        template_labels={"app": "web"},
        pod_template=Pod(name="t", containers=[Container(name="a")]),
    )
    # 默认滚动：可临时多 1 个，不可用时为 0（最稳妥，先增后删）
    assert dep.max_surge == 1
    assert dep.max_unavailable == 0


def test_taint_toleration():
    taint = Taint(key="gpu", effect="NoSchedule")
    # 不容忍 → 被排斥
    assert not taint.tolerated_by([])
    # 容忍同 key+effect → 通过
    assert taint.tolerated_by([Toleration(key="gpu", effect="NoSchedule")])
