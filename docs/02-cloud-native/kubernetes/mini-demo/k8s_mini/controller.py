"""controller.py — Deployment / ReplicaSet 控制器的教学模拟。

复刻真实控制器的范式（watch → inform → reconcile，水平触发）：
  - ReplicaSetController：维持每个 RS 的副本数（创建/删除 Pod 使之匹配）
  - DeploymentController：管理多个 RS（新/旧），按 maxSurge/maxUnavailable 滚动升级
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_mini.apiserver import ApiServer
from k8s_mini.model import Condition, Deployment, Pod, PodPhase, ReplicaSet


def _template_hash(dep: Deployment) -> str:
    """模板指纹：模板变化即视为新版本（真实 K8s 用 pod-template-hash）。"""
    import hashlib
    spec_blob = ",".join(
        f"{c.name}:{c.image}:{c.requests}" for c in dep.pod_template.containers
    )
    return hashlib.md5(spec_blob.encode()).hexdigest()[:8]


@dataclass
class ReplicaSetController:
    api: ApiServer
    stats: dict[str, int] = field(default_factory=lambda: {"pods_created": 0, "pods_deleted": 0})

    def reconcile(self) -> None:
        for rs in list(self.api.list_replicasets()):
            self._reconcile_rs(rs)
        self._garbage_collect_orphan_pods()

    def _garbage_collect_orphan_pods(self) -> None:
        """级联删除：owner_rs 指向的 ReplicaSet 已不存在时，删除该 Pod。

        对应真实 K8s 的 owner-reference + garbage collector。
        """
        live_rs = {rs.name for rs in self.api.list_replicasets()}
        for p in list(self.api.list_pods()):
            if p.owner_rs and p.owner_rs not in live_rs:
                self.api.delete_pod(p.name)

    def _reconcile_rs(self, rs: ReplicaSet) -> None:
        owned = [
            p for p in self.api.list_pods()
            if p.owner_rs == rs.name and rs.matches(p)
        ]
        running = [p for p in owned if p.phase != PodPhase.SUCCEEDED]
        diff = rs.replicas - len(running)
        if diff > 0:
            for _ in range(diff):
                self._create_pod(rs)
        elif diff < 0:
            # 删除多余的（按名字确定性）
            for p in sorted(running, key=lambda p: p.name)[: -diff]:
                self.api.delete_pod(p.name)
                self.stats["pods_deleted"] += 1

    def _create_pod(self, rs: ReplicaSet) -> None:
        tpl = rs.pod_template
        import copy
        pod = copy.deepcopy(tpl)
        idx = self._next_index(rs.name)
        pod.name = f"{rs.name}-{idx}"
        pod.owner_rs = rs.name
        pod.labels = {**tpl.labels, **rs.template_labels}
        pod.phase = PodPhase.PENDING
        pod.conditions = set()
        pod.node_name = ""
        pod.started_at_tick = -1
        pod.ready_at_tick = -1
        pod.pod_ip = ""
        self.api.create_pod(pod)
        self.stats["pods_created"] += 1

    def _next_index(self, rs_name: str) -> int:
        existing = [
            p for p in self.api.list_pods()
            if p.name.startswith(f"{rs_name}-")
        ]
        used = set()
        for p in existing:
            suffix = p.name.split("-")[-1]
            if suffix.isdigit():
                used.add(int(suffix))
        i = 0
        while i in used:
            i += 1
        return i


@dataclass
class DeploymentController:
    api: ApiServer
    rsc: ReplicaSetController
    stats: dict[str, int] = field(default_factory=lambda: {"rs_created": 0, "rollouts": 0})

    def reconcile(self) -> None:
        for dep in list(self.api.list_deployments()):
            self._reconcile_deployment(dep)

    def _reconcile_deployment(self, dep: Deployment) -> None:
        all_rs = [
            rs for rs in self.api.list_replicasets()
            if rs.owner_deployment == dep.name
        ]
        desired_hash = _template_hash(dep)

        # 确保当前版本 RS 存在
        current = next((rs for rs in all_rs if rs.name.endswith(desired_hash)), None)
        if current is None:
            current = ReplicaSet(
                name=f"{dep.name}-{desired_hash}",
                replicas=0,
                template_labels=dep.template_labels,
                pod_template=dep.pod_template,
                owner_deployment=dep.name,
            )
            self.api.create_replicaset(current)
            self.stats["rs_created"] += 1
            all_rs.append(current)

        new_rs = current
        old_rs = [rs for rs in all_rs if rs.name != new_rs.name]

        # 统计新/旧 RS 的就绪 Pod 数
        def ready_count(rs_name: str) -> int:
            return sum(
                1 for p in self.api.list_pods()
                if p.owner_rs == rs_name and Condition.POD_READY in p.conditions
            )

        new_ready = ready_count(new_rs.name)
        old_replicas = sum(r.replicas for r in old_rs)

        # 1. Surge：新 RS 向 replicas 增长，受 (replicas + max_surge - old) 上限约束
        surge_cap = dep.replicas + dep.max_surge - old_replicas
        target_new = min(dep.replicas, max(0, surge_cap))
        if new_rs.replicas < target_new:
            new_rs.replicas += 1
            self.api.update_replicaset(new_rs)

        # 2. Drain：当新 RS 就绪数足够维持 (replicas - max_unavailable) 可用时，缩旧
        if old_rs:
            old_ready = sum(ready_count(r.name) for r in old_rs)
            available_after_drain = new_ready + old_ready - 1
            if (new_ready > 0
                    and available_after_drain >= dep.replicas - dep.max_unavailable):
                # 选副本最多的旧 RS 缩 1（确定性）
                victim_rs = max(old_rs, key=lambda r: (r.replicas, r.name))
                if victim_rs.replicas > 0:
                    victim_rs.replicas -= 1
                    self.api.update_replicaset(victim_rs)
                    self.stats["rollouts"] += 1

        # 3. 清理已缩到 0 的旧 RS（真实 K8s 保留 revision 用于回滚，这里简化删除）
        for rs in list(old_rs):
            if rs.replicas == 0:
                self.api.delete_replicaset(rs.name)
