"""kubelet.py — 节点代理的教学模拟。

复刻真实 kubelet 的核心：
  - watch 分配到本节点（nodeName==self）的 Pod
  - PLEG：周期性对比"期望 vs 实际容器状态"，产生事件触发 syncPod
  - syncPod：调用 CRI 起容器、CNI 配网络、CSI 挂卷、Device Plugin 分配 GPU
  - 执行探针（startup/readiness/liveness），周期上报 Pod/Node 状态
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_mini.apiserver import ApiServer
from k8s_mini.device_plugin import GpuDevicePlugin
from k8s_mini.model import Condition, Node, Pod, PodPhase, Resources


@dataclass
class Kubelet:
    """单节点 kubelet。tick 驱动：每个 tick 模拟 PLEG + syncPod + 探针。"""

    node_name: str
    api: ApiServer
    gpu_plugin: GpuDevicePlugin | None = None
    # Pod 启动到 ready 需要的 tick 数（模拟模型加载/镜像拉取）
    startup_ticks: int = 1
    # 已分配 GPU 的 Pod -> 设备索引
    _pod_gpus: dict[str, list[int]] = field(default_factory=dict)
    # Pod -> 已运行 tick 计数
    _age: dict[str, int] = field(default_factory=dict)

    @property
    def node(self) -> Node:
        n = self.api.get_node(self.node_name)
        assert n is not None, f"node {self.node_name} not registered"
        return n

    def reconcile(self, tick: int) -> None:
        """一个 tick：对所有 nodeName==self 的 Pod 做 syncPod 收敛。"""
        node = self.node
        mine = [p for p in self.api.list_pods() if p.node_name == self.node_name]
        for pod in mine:
            self._sync_pod(pod, node, tick)

    def _sync_pod(self, pod: Pod, node: Node, tick: int) -> None:
        # 幂等收敛：只做必要的动作
        if pod.phase in (PodPhase.SUCCEEDED, PodPhase.FAILED):
            return
        if pod.started_at_tick < 0:
            # —— 启动路径（对应 syncPod 创建容器）——
            # 1. Device Plugin 分配 GPU（若有 gpu 请求）
            gpu_req = pod.total_request.gpu
            if gpu_req > 0 and self.gpu_plugin is not None:
                if self.gpu_plugin.free < gpu_req:
                    # GPU 不足（调度时预占与运行时分配不一致的兜底），标记失败
                    pod.phase = PodPhase.FAILED
                    self.api.update_pod(pod)
                    return
                idx = self.gpu_plugin.allocate(gpu_req)
                self._pod_gpus[pod.name] = idx
                pod.gpu_devices = list(idx)
            # 2. CRI/CNI/CSI（教学版无操作，仅记录启动时刻）
            pod.started_at_tick = tick
            pod.phase = PodPhase.RUNNING
            pod.pod_ip = f"10.{self._ip_byte()}.0.{self._port()}"
            self.api.update_pod(pod)
            self._age[pod.name] = 0
            return

        # —— 探针路径：模拟 startup→readiness ——
        self._age[pod.name] = self._age.get(pod.name, 0) + 1
        if Condition.CONTAINERS_READY not in pod.conditions and self._age[pod.name] >= self.startup_ticks:
            pod.conditions.add(Condition.CONTAINERS_READY)
            pod.conditions.add(Condition.POD_READY)
            pod.ready_at_tick = tick
            self.api.update_pod(pod)

    def _ip_byte(self) -> int:
        # 由节点名生成稳定的网段（确定性）
        return (sum(ord(c) for c in self.node_name) % 200) + 10

    def _port(self) -> int:
        return (sum(ord(c) for c in self.node_name) % 250) + 2

    def cleanup_pod(self, pod_name: str) -> None:
        """Pod 被驱逐/删除时回收 GPU。"""
        if pod_name in self._pod_gpus and self.gpu_plugin is not None:
            self.gpu_plugin.release(self._pod_gpus.pop(pod_name))
        self._age.pop(pod_name, None)
