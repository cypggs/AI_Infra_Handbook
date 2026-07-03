"""test_scheduler.py — kube-scheduler / 调度框架模拟测试。

覆盖 Filter / Score / Reserve / Bind / PostFilter(抢占) 扩展点：
  - binpack：3 个 Pod 聚到 1 个节点（密度优先）
  - spread：3 个 Pod 打散到 3 个节点（容错优先）
  - NodeAffinity（nodeSelector）过滤
  - TaintToleration 过滤
  - 资源不足时 PostFilter 抢占低优先级 Pod
"""

from k8s_mini.apiserver import ApiServer
from k8s_mini.model import Container, Node, Pod, PriorityClass, Resources, Taint, Toleration
from k8s_mini.scheduler import Scheduler, SchedulerConfig, SchedulingStrategy
from k8s_mini.store import Store


def _cluster():
    api = ApiServer(Store())
    return api, Scheduler(api)


def _basic_pod(name, cpu=1000, mem=1000):
    return Pod(name=name, containers=[Container(name="main", requests=Resources(cpu, mem))],
               labels={"app": name})


def _three_equal_nodes(api, cpu=4000, mem=8000):
    for nm in ("node-a", "node-b", "node-c"):
        api.register_node(Node(name=nm, capacity=Resources(cpu, mem)))


# ----------------------------- binpack -----------------------------

def test_binpack_packs_pods_onto_one_node():
    api, sched = _cluster()
    _three_equal_nodes(api)
    sched.config = SchedulerConfig(strategy=SchedulingStrategy.BINPACK)
    for i in range(3):
        api.create_pod(_basic_pod(f"p{i}"))
    sched.run_once()
    counts = {n.name: 0 for n in api.list_nodes()}
    for p in api.list_pods():
        if p.node_name:
            counts[p.node_name] += 1
    # 三个 Pod 全部落在同一个节点
    assert max(counts.values()) == 3
    assert sum(1 for c in counts.values() if c > 0) == 1


# ----------------------------- spread -----------------------------

def test_spread_distributes_evenly():
    api, sched = _cluster()
    _three_equal_nodes(api)
    sched.config = SchedulerConfig(strategy=SchedulingStrategy.SPREAD)
    for i in range(3):
        api.create_pod(_basic_pod(f"p{i}"))
    sched.run_once()
    counts = {n.name: 0 for n in api.list_nodes()}
    for p in api.list_pods():
        if p.node_name:
            counts[p.node_name] += 1
    # 每个节点恰好 1 个
    assert sorted(counts.values()) == [1, 1, 1]


# ----------------------------- NodeAffinity -----------------------------

def test_node_selector_restricts_placement():
    api, sched = _cluster()
    api.register_node(Node(name="node-a", capacity=Resources(4000, 8000), labels={"zone": "a"}))
    api.register_node(Node(name="node-b", capacity=Resources(4000, 8000), labels={"zone": "b"}))
    p = _basic_pod("p0")
    p.node_selector = {"zone": "b"}
    api.create_pod(p)
    sched.run_once()
    assert p.node_name == "node-b"


def test_node_selector_no_match_leaves_pending():
    api, sched = _cluster()
    api.register_node(Node(name="node-a", capacity=Resources(4000, 8000), labels={"zone": "a"}))
    p = _basic_pod("p0")
    p.node_selector = {"zone": "zzz"}
    api.create_pod(p)
    sched.run_once()
    assert p.node_name == ""
    assert sched.stats["filtered_out"] >= 1


# ----------------------------- TaintToleration -----------------------------

def test_taint_blocks_until_toleration():
    api, sched = _cluster()
    # 仅一个被污点的节点：不容忍者进不去，容忍者可进
    api.register_node(Node(
        name="gpu-node", capacity=Resources(4000, 8000),
        taints=[Taint(key="nvidia.com/gpu", effect="NoSchedule")],
    ))

    # 不容忍 → 被过滤，留在 Pending
    plain = _basic_pod("plain")
    api.create_pod(plain)
    sched.run_once()
    assert plain.node_name == ""
    assert sched.stats["filtered_out"] >= 1

    # 容忍 → 可进入 gpu-node
    tol = _basic_pod("tolerant")
    tol.tolerations = [Toleration(key="nvidia.com/gpu", effect="NoSchedule")]
    api.create_pod(tol)
    sched.run_once()
    assert tol.node_name == "gpu-node"


# ----------------------------- 抢占（PostFilter）-----------------------------

def test_preemption_evicts_lower_priority_pod():
    api, sched = _cluster()
    sched.config = SchedulerConfig(strategy=SchedulingStrategy.BINPACK, enable_preemption=True)
    # 单节点，正好放 1 个 2 核 Pod
    api.register_node(Node(name="n1", capacity=Resources(2000, 2000)))

    low = _basic_pod("low", cpu=2000)
    low.priority = PriorityClass("low", value=1)
    api.create_pod(low)
    sched.run_once()        # low 被调度，占满节点
    assert low.node_name == "n1"

    high = _basic_pod("high", cpu=2000)
    high.priority = PriorityClass("high", value=100)
    api.create_pod(high)
    sched.run_once()        # high 放不下 → 抢占 low

    # high 取代 low
    assert high.node_name == "n1"
    assert api.get_pod("low") is None
    assert sched.stats["preempted"] >= 1


def test_no_preemption_when_disabled():
    api, sched = _cluster()
    sched.config = SchedulerConfig(strategy=SchedulingStrategy.BINPACK, enable_preemption=False)
    api.register_node(Node(name="n1", capacity=Resources(2000, 2000)))
    low = _basic_pod("low", cpu=2000)
    low.priority = PriorityClass("low", value=1)
    api.create_pod(low)
    sched.run_once()
    high = _basic_pod("high", cpu=2000)
    high.priority = PriorityClass("high", value=100)
    api.create_pod(high)
    sched.run_once()
    # 关闭抢占：high 留在 Pending，low 不动
    assert high.node_name == ""
    assert api.get_pod("low") is not None
