"""apiserver.py — kube-apiserver 的极简模拟。

保留真实 apiserver 的核心链路：
  AuthN → AuthZ → Mutating Admission → Validating Admission → schema → 写 etcd(Store)
本模拟聚焦 Validating Admission（资源声明校验）与"写 Store + 通知 watcher"。
"""

from __future__ import annotations

from typing import Callable

from k8s_mini.model import Deployment, Node, Pod, ReplicaSet
from k8s_mini.store import Store


class AdmissionError(Exception):
    """Validating Admission 拒绝（真实 apiserver 会返回 403）。"""


class ApiServer:
    KIND = {"pod": "pod", "node": "node", "deployment": "deployment", "replicaset": "replicaset"}

    def __init__(self, store: Store) -> None:
        self.store = store
        # Validating Admission Webhooks（生产可用 Kyverno/OPA Gatekeeper）
        self._validating_hooks: list[Callable[[str, object], None]] = []
        # Mutating Admission Webhooks（如注入 sidecar、补默认值）
        self._mutating_hooks: list[Callable[[str, object], None]] = []

    def add_validating_hook(self, fn: Callable[[str, object], None]) -> None:
        self._validating_hooks.append(fn)

    def add_mutating_hook(self, fn: Callable[[str, object], None]) -> None:
        self._mutating_hooks.append(fn)

    # ---- 准入链 ----
    def _admit(self, kind: str, obj: object) -> None:
        # Mutating：可改对象
        for hook in self._mutating_hooks:
            hook(kind, obj)
        # Validating：只校验，抛 AdmissionError 即拒绝
        for hook in self._validating_hooks:
            hook(kind, obj)

    # ---- Pod ----
    def create_pod(self, pod: Pod) -> Pod:
        self._admit("pod", pod)
        return self.store.put("pod", pod.name, pod)

    def update_pod(self, pod: Pod) -> Pod:
        self._admit("pod", pod)
        return self.store.put("pod", pod.name, pod)

    def delete_pod(self, name: str) -> Pod | None:
        return self.store.delete("pod", name)

    def get_pod(self, name: str) -> Pod | None:
        return self.store.get("pod", name)

    def list_pods(self) -> list[Pod]:
        return self.store.all_of("pod")

    # ---- Node ----
    def register_node(self, node: Node) -> Node:
        return self.store.put("node", node.name, node)

    def update_node(self, node: Node) -> Node:
        return self.store.put("node", node.name, node)

    def list_nodes(self) -> list[Node]:
        return self.store.all_of("node")

    def get_node(self, name: str) -> Node | None:
        return self.store.get("node", name)

    # ---- Deployment / ReplicaSet ----
    def create_deployment(self, dep: Deployment) -> Deployment:
        self._admit("deployment", dep)
        return self.store.put("deployment", dep.name, dep)

    def update_deployment(self, dep: Deployment) -> Deployment:
        return self.store.put("deployment", dep.name, dep)

    def list_deployments(self) -> list[Deployment]:
        return self.store.all_of("deployment")

    def create_replicaset(self, rs: ReplicaSet) -> ReplicaSet:
        return self.store.put("replicaset", rs.name, rs)

    def update_replicaset(self, rs: ReplicaSet) -> ReplicaSet:
        return self.store.put("replicaset", rs.name, rs)

    def delete_replicaset(self, name: str) -> ReplicaSet | None:
        return self.store.delete("replicaset", name)

    def list_replicasets(self) -> list[ReplicaSet]:
        return self.store.all_of("replicaset")


def require_resources_hook(kind: str, obj: object) -> None:
    """生产级 Admission 示例：Pod 必须声明 resources.requests。

    真实场景：很多平台强制 GPU Pod 必须设 priority/资源声明，避免误调度。
    """
    if kind == "pod" and isinstance(obj, Pod):
        for c in obj.containers:
            if c.requests.cpu == 0 and c.requests.memory == 0:
                raise AdmissionError(
                    f"container '{c.name}' in pod '{obj.name}' must set resources.requests"
                )
