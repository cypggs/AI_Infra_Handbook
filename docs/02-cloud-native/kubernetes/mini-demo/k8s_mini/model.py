"""model.py — 资源、节点、Pod、Deployment/ReplicaSet 数据模型。

与真实 K8s 的对应：
  - Resources.requests 是调度依据（kube-scheduler 据此判断能否放下）
  - Resources.limits 是运行时上限（kubelet/CRI 据此设 cgroup）
  - Pod 是最小调度单元，PodPhase 是粗粒度状态机
  - Deployment 拥有 ReplicaSet，ReplicaSet 拥有 Pod（owner reference 链）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PodPhase(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class Condition(str, Enum):
    POD_SCHEDULED = "PodScheduled"
    CONTAINERS_READY = "ContainersReady"
    POD_READY = "PodReady"


@dataclass
class Resources:
    """资源数量。cpu 用毫核整数（1000m = 1 核），memory 用 MiB，gpu 用整数张。"""

    cpu: int = 0  # millicores
    memory: int = 0  # MiB
    gpu: int = 0  # nvidia.com/gpu

    def fits(self, other: "Resources") -> bool:
        """other 是否能放进 self（self 作为节点剩余容量）。"""
        return (
            self.cpu >= other.cpu
            and self.memory >= other.memory
            and self.gpu >= other.gpu
        )

    def add(self, other: "Resources") -> "Resources":
        return Resources(self.cpu + other.cpu, self.memory + other.memory, self.gpu + other.gpu)

    def sub(self, other: "Resources") -> "Resources":
        if not self.fits(other):
            raise ValueError(f"insufficient resources: {self} - {other}")
        return Resources(self.cpu - other.cpu, self.memory - other.memory, self.gpu - other.gpu)

    def __repr__(self) -> str:
        return f"cpu={self.cpu}m,mem={self.memory}Mi,gpu={self.gpu}"


@dataclass
class Taint:
    """节点污点。effect ∈ {NoSchedule, NoExecute}。"""

    key: str
    value: str = ""
    effect: str = "NoSchedule"

    def tolerated_by(self, tolerations: list["Toleration"]) -> bool:
        return any(t.key == self.key and t.effect == self.effect for t in tolerations)


@dataclass
class Toleration:
    key: str
    effect: str = "NoSchedule"


@dataclass
class Container:
    name: str
    image: str = "busybox"
    requests: Resources = field(default_factory=Resources)
    limits: Resources = field(default_factory=Resources)
    command: list[str] = field(default_factory=list)

    @property
    def total_request(self) -> Resources:
        """调度按 requests 算（K8s 真实行为：Pod 资源 = 各容器 requests 之和）。"""
        return self.requests


@dataclass
class PriorityClass:
    name: str
    value: int = 0  # 数值越大优先级越高
    preemptable: bool = True  # 是否可被高优先级 Pod 抢占


@dataclass
class Node:
    name: str
    capacity: Resources
    labels: dict[str, str] = field(default_factory=dict)
    taints: list[Taint] = field(default_factory=list)
    ready: bool = True

    # 运行时状态
    allocated: Resources = field(default_factory=Resources)
    pod_names: set[str] = field(default_factory=set)
    # 设备插件注册的扩展资源（如 nvidia.com/gpu）已并入 capacity.gpu

    @property
    def allocatable(self) -> Resources:
        return self.capacity.sub(self.allocated) if self._allocated_fits() else Resources()

    def _allocated_fits(self) -> bool:
        return self.capacity.fits(self.allocated)

    def allocate(self, r: Resources) -> None:
        self.allocated = self.allocated.add(r)

    def release(self, r: Resources) -> None:
        self.allocated = self.allocated.sub(r)


@dataclass
class Pod:
    name: str
    containers: list[Container]
    node_name: str = ""
    phase: PodPhase = PodPhase.PENDING
    conditions: set[Condition] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    node_selector: dict[str, str] = field(default_factory=dict)
    tolerations: list[Toleration] = field(default_factory=list)
    priority: PriorityClass = field(default_factory=lambda: PriorityClass("default", 0))
    # owner reference 链：Pod ← ReplicaSet ← Deployment
    owner_rs: str = ""
    # PodGroup（Gang 调度）：同一 gang_id 的 Pod 必须 all-or-nothing 调度
    gang_id: str = ""
    gang_min_available: int = 0  # 该 gang 至少要调度成功这么多 Pod 才放行

    # kubelet 运行时
    pod_ip: str = ""
    started_at_tick: int = -1
    ready_at_tick: int = -1  # 探针就绪时刻（模拟模型加载）
    restart_policy: str = "Always"
    # Device Plugin 分配的 GPU 设备索引（运行时由 kubelet 填充）
    gpu_devices: list[int] = field(default_factory=list)

    @property
    def total_request(self) -> Resources:
        r = Resources()
        for c in self.containers:
            r = r.add(c.total_request)
        return r

    @property
    def scheduled(self) -> bool:
        return Condition.POD_SCHEDULED in self.conditions

    @property
    def is_gang(self) -> bool:
        return self.gang_id != ""


@dataclass
class ReplicaSet:
    """ReplicaSet：维持某模板的副本数。Deployment 通过管理多个 RS 实现滚动升级。"""

    name: str
    replicas: int
    template_labels: dict[str, str]
    pod_template: Pod
    owner_deployment: str = ""
    # 标记本次 reconcile 期望创建的 Pod 数（被 RS 控制器读取）

    def matches(self, pod: Pod) -> bool:
        return all(pod.labels.get(k) == v for k, v in self.template_labels.items())


@dataclass
class Deployment:
    """Deployment：声明期望状态（replicas + 模板），由 DeploymentController reconcile。"""

    name: str
    replicas: int
    template_labels: dict[str, str]
    pod_template: Pod
    # 滚动升级参数
    max_surge: int = 1  # 最多可超出期望 replicas 多少
    max_unavailable: int = 0  # 滚动期间最多不可用多少
