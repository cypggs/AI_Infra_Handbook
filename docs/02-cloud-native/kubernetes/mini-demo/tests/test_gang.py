"""test_gang.py — Gang 调度（all-or-nothing，对应 KEP-4671）测试。

核心断言：
  - gang 成员数 ≥ min_available 且资源够 → 全部调度成功
  - 凑不够 min_available → 一个都不调度，且已预占的资源被回滚（all-or-nothing）
"""

from k8s_mini.apiserver import ApiServer
from k8s_mini.model import Container, Node, Pod, PriorityClass, Resources
from k8s_mini.scheduler import Scheduler, SchedulerConfig, SchedulingStrategy
from k8s_mini.store import Store


def _gang_pod(gang, idx, cpu=1000, mem=500, min_available=2):
    return Pod(
        name=f"{gang}-worker-{idx}",
        containers=[Container(name="trainer", requests=Resources(cpu, mem))],
        labels={"gang": gang},
        gang_id=gang,
        gang_min_available=min_available,
        priority=PriorityClass(f"{gang}-pri", value=10),
    )


def _cluster():
    api = ApiServer(Store())
    sched = Scheduler(api)
    sched.config = SchedulerConfig(strategy=SchedulingStrategy.SPREAD)
    return api, sched


def test_gang_succeeds_when_quorum_reachable():
    api, sched = _cluster()
    api.register_node(Node(name="n-a", capacity=Resources(2000, 2000)))
    api.register_node(Node(name="n-b", capacity=Resources(2000, 2000)))
    for i in range(2):
        api.create_pod(_gang_pod("gang-ok", i, min_available=2))
    sched.run_once()
    status = sched.gang_status()
    assert status["gang-ok"] == "2/2 scheduled"
    assert sched.stats["gang_bound"] == 2


def test_gang_all_or_nothing_with_rollback():
    """单节点 2 核；gang 要 3 个 1 核 worker 且 min_available=3。
    只放得下 2 个 → 不达法定数 → 全部回滚，节点资源恢复满，0 调度。"""
    api, sched = _cluster()
    node = Node(name="n1", capacity=Resources(2000, 2000))
    api.register_node(node)
    for i in range(3):
        api.create_pod(_gang_pod("gang-bad", i, cpu=1000, min_available=3))
    sched.run_once()

    status = sched.gang_status()
    assert status["gang-bad"] == "0/3 scheduled"
    assert sched.stats["gang_rejected"] >= 1
    # 回滚：节点资源未被占用
    assert (node.allocated.cpu, node.allocated.memory) == (0, 0)
    # 没有任何 gang Pod 被绑定
    assert all(not p.scheduled for p in api.list_pods())


def test_two_gangs_independent_outcome():
    """同 demo 场景：gang-ok 全调度，gang-fail 资源不足整体拒绝。"""
    api, sched = _cluster()
    api.register_node(Node(name="g-node-a", capacity=Resources(2000, 2000)))
    api.register_node(Node(name="g-node-b", capacity=Resources(2000, 2000)))

    for i in range(2):
        api.create_pod(_gang_pod("gang-ok", i, cpu=1000, min_available=2))
    for i in range(3):
        p = _gang_pod("gang-fail", i, cpu=2000, min_available=3)
        api.create_pod(p)

    sched.run_once()
    status = sched.gang_status()
    assert status["gang-ok"] == "2/2 scheduled"
    assert status["gang-fail"] == "0/3 scheduled"
