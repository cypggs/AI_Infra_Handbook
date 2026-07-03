"""demo.py — k8s_mini 入口演示：四个场景串起 Kubernetes 的核心机制。

场景：
  1. 基础调度（binpack vs spread）：同一批 Pod 在两种打分策略下的落点差异
  2. GPU 调度：带 nvidia.com/gpu 请求的 Pod 如何被 Device Plugin 分配并调度
  3. Deployment 滚动升级 + 自愈：模板变更触发滚动；删 Pod 触发 RS 控制器补齐
  4. Gang 调度（all-or-nothing）：训练 Job 的多 Pod 要么全调度成功要么全失败

每个场景都用确定性模拟（无随机、无真实网络），可在 CPU 上反复运行得到相同结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_mini.apiserver import ApiServer
from k8s_mini.controller import DeploymentController, ReplicaSetController
from k8s_mini.device_plugin import GpuDevicePlugin
from k8s_mini.kubelet import Kubelet
from k8s_mini.model import (
    Condition,
    Container,
    Deployment,
    Node,
    Pod,
    PodPhase,
    PriorityClass,
    Resources,
    Taint,
    Toleration,
)
from k8s_mini.observer import Observer
from k8s_mini.scheduler import Scheduler, SchedulerConfig, SchedulingStrategy
from k8s_mini.store import Store


# ----------------------------- 集群编排器 -----------------------------

@dataclass
class MiniCluster:
    """把 apiserver + scheduler + kubelets + controllers 组成一个可 tick 的集群。"""

    api: ApiServer = field(default_factory=lambda: ApiServer(Store()))
    scheduler: Scheduler = field(init=False)
    rsc: ReplicaSetController = field(init=False)
    depc: DeploymentController = field(init=False)
    observer: Observer = field(default_factory=Observer)
    kubelets: dict[str, Kubelet] = field(default_factory=dict)
    gpu_plugins: dict[str, GpuDevicePlugin] = field(default_factory=dict)
    tick: int = 0

    def __post_init__(self) -> None:
        self.api.store.add_watcher(self.observer.on_event)
        self.scheduler = Scheduler(self.api)
        self.rsc = ReplicaSetController(self.api)
        self.depc = DeploymentController(self.api, self.rsc)

    def set_strategy(self, strategy: str) -> None:
        self.scheduler.config = SchedulerConfig(strategy=strategy)

    def add_node(self, name: str, cpu: int, memory: int, gpu: int = 0,
                 labels: dict[str, str] | None = None,
                 taints: list[Taint] | None = None) -> Node:
        # gpu 容量由 Device Plugin 注册时上报（模拟真实 K8s：扩展资源来自 device plugin）
        node = Node(name=name, capacity=Resources(cpu, memory, 0),
                    labels=labels or {}, taints=taints or [])
        self.api.register_node(node)
        plugin = None
        if gpu > 0:
            plugin = GpuDevicePlugin(name, gpu)
            plugin.register(node)  # 把 nvidia.com/gpu 容量并入 capacity
            self.gpu_plugins[name] = plugin
        self.api.update_node(node)
        self.kubelets[name] = Kubelet(name, self.api, gpu_plugin=plugin, startup_ticks=1)
        return node

    def run(self, ticks: int = 5) -> None:
        """推进 ticks 个控制循环周期（每 tick：控制器→调度器→kubelet）。"""
        for _ in range(ticks):
            self.observer.set_tick(self.tick)
            # 1. 控制器先跑（生成/删除 Pod）
            self.depc.reconcile()
            self.rsc.reconcile()
            # 2. 调度器把 Pending Pod 绑定到节点
            self.scheduler.run_once()
            # 3. 各节点 kubelet 启动 Pod 并上报状态
            for kl in self.kubelets.values():
                kl.reconcile(self.tick)
            self.tick += 1

    # ---- 便捷断言用 ----
    def pods_on(self, node_name: str) -> list[Pod]:
        return [p for p in self.api.list_pods() if p.node_name == node_name]

    def ready_pods(self) -> list[Pod]:
        return [p for p in self.api.list_pods() if Condition.POD_READY in p.conditions]

    def running_pods(self) -> list[Pod]:
        return [p for p in self.api.list_pods() if p.phase == PodPhase.RUNNING]


def _basic_pod(name: str, cpu: int = 1000, mem: int = 1024) -> Pod:
    return Pod(
        name=name,
        containers=[Container(name="main", requests=Resources(cpu, mem))],
        labels={"app": name},
    )


# ----------------------------- 场景 1：调度策略 -----------------------------

def scenario_scheduling() -> dict:
    c = MiniCluster()
    # 三个等量节点
    c.add_node("node-a", cpu=4000, memory=8000)
    c.add_node("node-b", cpu=4000, memory=8000)
    c.add_node("node-c", cpu=4000, memory=8000)

    # binpack：应聚到一个节点
    c.set_strategy(SchedulingStrategy.BINPACK)
    for i in range(3):
        c.api.create_pod(_basic_pod(f"binpack-{i}", cpu=1000, mem=1000))
    c.run(ticks=2)
    binpack_dist = {n.name: len(c.pods_on(n.name)) for n in c.api.list_nodes()}

    # spread：应打散
    c2 = MiniCluster()
    c2.add_node("node-a", cpu=4000, memory=8000)
    c2.add_node("node-b", cpu=4000, memory=8000)
    c2.add_node("node-c", cpu=4000, memory=8000)
    c2.set_strategy(SchedulingStrategy.SPREAD)
    for i in range(3):
        c2.api.create_pod(_basic_pod(f"spread-{i}", cpu=1000, mem=1000))
    c2.run(ticks=2)
    spread_dist = {n.name: len(c2.pods_on(n.name)) for n in c2.api.list_nodes()}

    return {"binpack": binpack_dist, "spread": spread_dist}


# ----------------------------- 场景 2：GPU 调度 -----------------------------

def scenario_gpu() -> dict:
    c = MiniCluster()
    # 两个 GPU 节点，各 2 张卡
    c.add_node("gpu-node-1", cpu=8000, memory=16000, gpu=2)
    c.add_node("gpu-node-2", cpu=8000, memory=16000, gpu=2)

    def gpu_pod(name: str) -> Pod:
        return Pod(
            name=name,
            containers=[Container(name="vllm", image="vllm/vllm",
                                  requests=Resources(cpu=2000, memory=4096, gpu=1))],
            labels={"app": "vllm"},
        )

    for i in range(3):  # 需要 3 张 GPU
        c.api.create_pod(gpu_pod(f"vllm-{i}"))
    c.run(ticks=3)

    placed = [(p.name, p.node_name, p.phase.value, p.gpu_devices)
              for p in c.api.list_pods()]
    return {"placed": placed, "free": {n: c.gpu_plugins[n].free for n in c.gpu_plugins}}


# ----------------------------- 场景 3：滚动升级 + 自愈 -----------------------------

def scenario_rollout() -> dict:
    c = MiniCluster()
    c.add_node("node-a", cpu=4000, memory=8000)
    c.add_node("node-b", cpu=4000, memory=8000)
    c.set_strategy(SchedulingStrategy.SPREAD)

    base = Pod(name="web-template",
               containers=[Container(name="app", image="app:v1",
                                     requests=Resources(1000, 1024))],
               labels={"app": "web"})
    dep = Deployment(name="web", replicas=3, template_labels={"app": "web"}, pod_template=base)
    c.api.create_deployment(dep)
    c.run(ticks=3)

    v1_running = [p.name for p in c.running_pods()]

    # 滚动升级到 v2
    dep.pod_template.containers[0].image = "app:v2"
    c.api.update_deployment(dep)
    c.run(ticks=10)

    v2_running = [p.name for p in c.running_pods()]
    images = {p.name: p.containers[0].image for p in c.api.list_pods() if p.phase == PodPhase.RUNNING}

    # 自愈：删一个 Pod，RS 控制器应补齐
    before = len(c.running_pods())
    if c.running_pods():
        victim = c.running_pods()[0]
        c.api.delete_pod(victim.name)
    c.run(ticks=3)
    after = len(c.running_pods())

    return {"v1_pods": v1_running, "v2_pods": v2_running, "images_after_rollout": images,
            "self_heal_before": before, "self_heal_after": after}


# ----------------------------- 场景 4：Gang 调度 -----------------------------

def scenario_gang() -> dict:
    """两个 gang：一个能全调度成功，一个资源不足应被整体拒绝。"""
    c = MiniCluster()
    # 总共只能放 3 个 1-CPU Pod（两个节点各 cpu=2000，每个 gang 成员要 1000）
    c.add_node("g-node-a", cpu=2000, memory=2000)
    c.add_node("g-node-b", cpu=2000, memory=2000)
    c.set_strategy(SchedulingStrategy.SPREAD)

    def gang_pod(gang: str, idx: int) -> Pod:
        return Pod(
            name=f"{gang}-worker-{idx}",
            containers=[Container(name="trainer", requests=Resources(1000, 500))],
            labels={"gang": gang},
            gang_id=gang,
            gang_min_available=2,  # 每个 gang 至少 2 个 worker 才能 all-or-nothing
            priority=PriorityClass(f"{gang}-pri", value=10),
        )

    # gang-ok：2 worker，资源够 → 全部调度
    c.api.create_pod(gang_pod("gang-ok", 0))
    c.api.create_pod(gang_pod("gang-ok", 1))
    # gang-fail：3 worker 但只剩 2 CPU → min_available=2 时凑得到
    # 改成更大请求让它凑不够：每个要 2000m，两个节点共 4000m，但 gang-ok 已占 2000
    for i in range(3):
        p = gang_pod("gang-fail", i)
        p.containers[0].requests = Resources(2000, 500)  # 每个 2 核
        p.gang_min_available = 3
        c.api.create_pod(p)
    c.run(ticks=2)

    return {
        "gang_status": c.scheduler.gang_status(),
        "gang_ok_scheduled": sum(1 for p in c.api.list_pods()
                                 if p.gang_id == "gang-ok" and p.scheduled),
        "gang_fail_scheduled": sum(1 for p in c.api.list_pods()
                                   if p.gang_id == "gang-fail" and p.scheduled),
    }


# ----------------------------- 入口 -----------------------------

def run_demo() -> None:
    print("=" * 70)
    print("Mini Kubernetes — 调度框架 / GPU / 滚动 / Gang 调度演示")
    print("=" * 70)

    print("\n[场景 1] 调度策略：binpack vs spread")
    r1 = scenario_scheduling()
    print(f"  binpack 分布: {r1['binpack']}   ← Pod 聚到一个节点（提高密度）")
    print(f"  spread  分布: {r1['spread']}   ← Pod 打散到不同节点（容错）")

    print("\n[场景 2] GPU 调度：Device Plugin 分配 nvidia.com/gpu")
    r2 = scenario_gpu()
    for name, node, phase, alloc in r2["placed"]:
        print(f"  {name} → {node} ({phase}), GPU devices allocated={sorted(alloc)}")
    print(f"  节点剩余 GPU: {r2['free']}")

    print("\n[场景 3] Deployment 滚动升级 + 自愈")
    r3 = scenario_rollout()
    print(f"  v1 阶段 Pod: {r3['v1_pods']}")
    print(f"  v2 阶段 Pod: {r3['v2_pods']}")
    print(f"  滚动后镜像: {r3['images_after_rollout']}")
    print(f"  自愈: 删除前 running={r3['self_heal_before']} → 补齐后 running={r3['self_heal_after']}")

    print("\n[场景 4] Gang 调度（all-or-nothing）")
    r4 = scenario_gang()
    print(f"  各 gang 状态: {r4['gang_status']}")
    print(f"  gang-ok  已调度: {r4['gang_ok_scheduled']}（应=2，全部成功）")
    print(f"  gang-fail 已调度: {r4['gang_fail_scheduled']}（应=0，资源不足整体拒绝）")

    print("\n" + "=" * 70)
    print("演示完成。所有场景均为确定性模拟，可反复运行得到相同结果。")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
