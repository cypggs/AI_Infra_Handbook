"""demo.py —— 六个端到端 GPU 调度场景演示。

运行方式：
    cd docs/02-cloud-native/gpu-scheduling/mini-demo
    python -m gpu_scheduling_mini.demo
"""
from . import model
from .apiserver import FakeApiServer
from .clock import FakeClock
from .device_plugin import DevicePlugin
from .kubelet import Kubelet
from .scheduler import Scheduler
from .topology import Topology, TopologyScorer
from .gang import GangScheduler, PodGroupState


def _make_gpu_node(name, gpu_count, topology=None, mig=None):
    """构造带 GPU 的节点并注册到 apiserver。"""
    node = model.make_node(name, gpu_count=gpu_count, mig_devices=mig or {}, topology=topology)
    return node


def scenario_1_device_plugin_registration():
    """场景 1：Device Plugin 注册与单卡分配。"""
    print("\n=== 场景 1：Device Plugin 注册与单卡分配 ===")
    api = FakeApiServer()
    clock = FakeClock()

    node = _make_gpu_node("node-1", 4)
    api.create(node)

    kubelet = Kubelet(api, "node-1")
    plugin = DevicePlugin(model.GPU_RESOURCE, node["status"]["devices"], clock=clock)
    plugin.register(kubelet)

    pod = model.make_pod("train-0", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 1}},
    }])
    pod["spec"]["nodeName"] = "node-1"
    api.create(pod)

    kubelet.sync_pod(pod)
    env = {e["name"]: e["value"] for e in pod["spec"]["containers"][0].get("env", [])}
    print(f"Pod phase: {pod['status']['phase']}")
    print(f"Allocated devices: {pod['status']['allocated_devices']}")
    print(f"NVIDIA_VISIBLE_DEVICES={env.get('NVIDIA_VISIBLE_DEVICES')}")
    assert pod["status"]["phase"] == "Running"
    assert "NVIDIA_VISIBLE_DEVICES" in env


def scenario_2_scheduler_filter_score_bind():
    """场景 2：Scheduler Filter/Score/Reserve/Bind。"""
    print("\n=== 场景 2：Scheduler Filter/Score/Reserve/Bind ===")
    api = FakeApiServer()

    api.create(_make_gpu_node("node-2", 2))
    api.create(_make_gpu_node("node-3", 4))

    scheduler = Scheduler(api)
    pod = model.make_pod("train-1", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 2}},
    }])
    api.create(pod)

    ok = scheduler.schedule_one(pod)
    print(f"Schedule success: {ok}")
    print(f"Pod bound to: {pod['spec']['nodeName']}")
    print(f"Allocated devices: {pod['status']['allocated_devices']}")
    assert ok
    assert pod["spec"]["nodeName"] in ("node-2", "node-3")
    assert len(pod["status"]["allocated_devices"][model.GPU_RESOURCE]) == 2


def scenario_3_mig_scheduling():
    """场景 3：MIG Profile 资源调度。"""
    print("\n=== 场景 3：MIG Profile 资源调度 ===")
    api = FakeApiServer()

    # 8 张 A100，每张切成 7 个 1g.5gb
    api.create(model.make_node("mig-node", gpu_count=0, mig_devices={"1g.5gb": 7}))

    scheduler = Scheduler(api)
    pod = model.make_pod("infer-0", containers=[{
        "name": "infer",
        "resources": {"requests": {f"{model.MIG_RESOURCE_PREFIX}1g.5gb": 2}},
    }])
    api.create(pod)

    ok = scheduler.schedule_one(pod)
    print(f"Schedule success: {ok}")
    print(f"Pod bound to: {pod['spec']['nodeName']}")
    print(f"Allocated MIG devices: {pod['status']['allocated_devices']}")
    assert ok


def scenario_4_gang_scheduling():
    """场景 4：PodGroup Gang 调度（all-or-nothing）。"""
    print("\n=== 场景 4：PodGroup Gang 调度（all-or-nothing） ===")
    api = FakeApiServer()

    api.create(_make_gpu_node("gang-node", 1))
    scheduler = Scheduler(api)
    gang = GangScheduler(api, scheduler)

    pg = model.make_podgroup("train-pg", min_member=2)
    api.create(pg)

    for i in range(2):
        pod = model.make_pod(f"gang-worker-{i}", pod_group_name="train-pg", containers=[{
            "name": "train",
            "resources": {"requests": {model.GPU_RESOURCE: 1}},
        }])
        api.create(pod)

    ok, msg = gang.schedule_group(pg)
    print(f"First attempt: ok={ok}, msg={msg}")
    # 只有 1 张卡，2 个 Pod 无法同时满足，应该失败
    assert not ok

    # 扩容节点后再调度（新增一张 1-GPU 节点，与原有节点各承载一个 worker）
    api.create(_make_gpu_node("gang-node-2", 1))
    ok, msg = gang.schedule_group(pg)
    print(f"Second attempt: ok={ok}, msg={msg}")
    assert ok
    assert pg["status"]["phase"] == PodGroupState.Scheduled


def scenario_5_topology_aware():
    """场景 5：拓扑感知打分（单节点 8-GPU 训练）。"""
    print("\n=== 场景 5：拓扑感知打分（单节点 8-GPU 训练） ===")
    api = FakeApiServer()

    topo = Topology(
        numa_nodes=[[0, 1, 2, 3], [4, 5, 6, 7]],
        pcie_switches=[[0, 1], [2, 3], [4, 5], [6, 7]],
        nvswitch_groups=[[0, 1, 2, 3, 4, 5, 6, 7]],
    )
    scorer = TopologyScorer(topo)

    api.create(_make_gpu_node("topo-node", 8, topology=topo))
    scheduler = Scheduler(api, topology_scorer=scorer)

    pod = model.make_pod("ddp-train", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 4}},
    }])
    api.create(pod)

    ok = scheduler.schedule_one(pod)
    print(f"Schedule success: {ok}")
    print(f"Allocated GPUs: {pod['status']['allocated_devices']}")
    assert ok
    indices = pod["status"]["allocated_devices"].get(model.GPU_RESOURCE, [])
    # 4 张卡应该落在同一个 NUMA（0-3 或 4-7）
    assert len(indices) == 4
    assert scorer.score_indices(indices) == TopologyScorer.SCORE_SAME_NUMA


def scenario_6_gpu_sharing():
    """场景 6：GPU 共享约束（MPS/time-slicing）。"""
    print("\n=== 场景 6：GPU 共享约束（MPS/time-slicing） ===")
    api = FakeApiServer()

    api.create(_make_gpu_node("shared-node", 1))
    scheduler = Scheduler(api)

    pods = []
    for i in range(10):
        pod = model.make_pod(f"shared-pod-{i}", containers=[{
            "name": "infer",
            "resources": {"requests": {model.GPU_SHARED_RESOURCE: 1}},
        }])
        api.create(pod)
        pods.append(pod)

    scheduled = 0
    for pod in pods:
        if scheduler.schedule_one(pod):
            scheduled += 1

    print(f"Scheduled {scheduled}/10 shared pods on 1 GPU")
    assert scheduled == 10

    # 第 11 个应该失败
    overflow = model.make_pod("shared-overflow", containers=[{
        "name": "infer",
        "resources": {"requests": {model.GPU_SHARED_RESOURCE: 1}},
    }])
    api.create(overflow)
    assert not scheduler.schedule_one(overflow)
    print("Overflow pod correctly rejected")


def run_all():
    scenario_1_device_plugin_registration()
    scenario_2_scheduler_filter_score_bind()
    scenario_3_mig_scheduling()
    scenario_4_gang_scheduling()
    scenario_5_topology_aware()
    scenario_6_gpu_sharing()
    print("\n✅ 全部 6 个 GPU 调度场景通过")


if __name__ == "__main__":
    run_all()
