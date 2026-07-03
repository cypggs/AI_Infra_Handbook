"""scheduler.py — kube-scheduler 与调度框架（Scheduling Framework）的教学模拟。

忠实复刻调度框架的关键设计（自 K8s v1.19 GA）：
  - 调度周期（Scheduling Cycle）：串行，Filter → Score → Reserve → Permit
  - 绑定周期（Binding Cycle）：可并发，Bind 把 nodeName 写回 apiserver
  - 12 个扩展点中的核心几个：PreFilter / Filter / PostFilter / Score / Reserve / Permit / Bind
  - Filter 插件：NodeResourcesFit、NodeAffinity(nodeSelector)、TaintToleration
  - Score 策略：binpack（装箱，偏好更满节点）/ spread（打散，偏好更空节点）/ balanced
  - PostFilter：抢占（驱逐低优先级 Pod 腾位）
  - Gang 调度（Permit + all-or-nothing）：同 gang_id 的 Pod 必须全部调度成功，否则全不调度
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_mini.apiserver import ApiServer
from k8s_mini.model import Condition, Node, Pod, Resources


class SchedulingStrategy(str):
    BINPACK = "binpack"
    SPREAD = "spread"
    BALANCED = "balanced"


@dataclass
class SchedulerConfig:
    strategy: str = SchedulingStrategy.BINPACK
    enable_preemption: bool = True


@dataclass
class Scheduler:
    api: ApiServer
    config: SchedulerConfig = field(default_factory=SchedulerConfig)
    # 统计：本 tick 内各阶段计数，供观测与测试
    stats: dict[str, int] = field(default_factory=lambda: {
        "scheduled": 0, "filtered_out": 0, "preempted": 0, "gang_bound": 0, "gang_rejected": 0,
    })

    # ===================== 调度周期（串行）=====================

    def run_once(self) -> None:
        """一个 tick 的调度：取出所有未调度 Pod，分组（gang 优先），逐个/成组调度。"""
        pending = [p for p in self.api.list_pods() if not p.scheduled and p.phase.value == "Pending"]
        # 先处理 gang：同 gang_id 的 Pod 要么全成要么全败
        gang_pods: dict[str, list[Pod]] = {}
        solo: list[Pod] = []
        for p in pending:
            if p.is_gang:
                gang_pods.setdefault(p.gang_id, []).append(p)
            else:
                solo.append(p)

        for gid, members in gang_pods.items():
            self._schedule_gang(members)
        for p in solo:
            self._schedule_one(p)

    # ---- 单 Pod 调度 ----
    def _schedule_one(self, pod: Pod) -> None:
        # 1. PreFilter
        req = pod.total_request
        # 2. Filter
        feasible = self._filter_nodes(pod, req)
        if not feasible:
            # 3. PostFilter：抢占
            if self.config.enable_preemption:
                node = self._try_preempt(pod, req)
                if node is not None:
                    self.stats["preempted"] += 1
                    self._reserve_and_bind(pod, node)
            return
        # 4. Score
        node = self._score(pod, feasible)
        # 5-6. Reserve + Bind
        self._reserve_and_bind(pod, node)

    # ---- Gang 调度（all-or-nothing，对应 KEP-4671）----
    def _schedule_gang(self, members: list[Pod]) -> None:
        if not members:
            return
        min_available = members[0].gang_min_available
        # 给每个成员尝试 Reserve（不立即 Bind）
        reserved: list[tuple[Pod, Node]] = []
        # 按优先级排序保证确定性
        members_sorted = sorted(members, key=lambda p: (-p.priority.value, p.name))
        used_nodes_snap: dict[str, Resources] = {}

        for p in members_sorted:
            if len(reserved) >= min_available:
                break
            req = p.total_request
            feasible = self._filter_nodes(p, req)
            if not feasible:
                continue
            node = self._score(p, feasible)
            # Reserve：在 node 上预占（真实调度框架的 Reserve 扩展点）
            node.allocate(req)
            reserved.append((p, node))

        if len(reserved) >= min_available:
            # 全部 Bind（Permit 放行）
            for p, node in reserved:
                self._bind(p, node)
            self.stats["gang_bound"] += len(reserved)
        else:
            # 失败：回滚所有预占（all-or-nothing）
            for p, node in reserved:
                node.release(p.total_request)
            self.stats["gang_rejected"] += 1

    # ===================== Filter 插件 =====================

    def _filter_nodes(self, pod: Pod, req: Resources) -> list[Node]:
        feasible: list[Node] = []
        for node in self.api.list_nodes():
            if not node.ready:
                continue
            if self._node_resources_fit(node, req) and self._node_affinity(node, pod) \
                    and self._taint_toleration(node, pod):
                feasible.append(node)
            else:
                self.stats["filtered_out"] += 1
        return feasible

    def _node_resources_fit(self, node: Node, req: Resources) -> bool:
        """NodeResourcesFit 插件：节点 allocatable 是否够放。"""
        return node.allocatable.fits(req)

    def _node_affinity(self, node: Node, pod: Pod) -> bool:
        """NodeAffinity / nodeSelector：节点 label 是否满足 Pod 要求。"""
        return all(node.labels.get(k) == v for k, v in pod.node_selector.items())

    def _taint_toleration(self, node: Node, pod: Pod) -> bool:
        """TaintToleration 插件：Pod 是否容忍节点的污点。"""
        for taint in node.taints:
            if not taint.tolerated_by(pod.tolerations):
                return False
        return True

    # ===================== Score 插件 =====================

    def _score(self, pod: Pod, feasible: list[Node]) -> Node:
        """按策略打分选节点。分数越高越优先。"""
        if self.config.strategy == SchedulingStrategy.SPREAD:
            # spread：偏好剩余容量多的节点（-已用率）
            return max(feasible, key=lambda n: (n.allocatable.cpu + n.allocatable.memory, n.name))
        if self.config.strategy == SchedulingStrategy.BALANCED:
            # balanced：放进去后 cpu/mem 利用率最接近（K8s NodeResourcesBalancedAllocation 思想）
            def balanced_score(n: Node) -> float:
                after = n.allocated.add(pod.total_request)
                cpu_ratio = after.cpu / n.capacity.cpu if n.capacity.cpu else 1
                mem_ratio = after.memory / n.capacity.memory if n.capacity.memory else 1
                return -(abs(cpu_ratio - mem_ratio))
            return max(feasible, key=balanced_score)
        # 默认 binpack：偏好已用最多的节点（装箱，提高密度）
        return max(feasible, key=lambda n: (n.allocated.cpu + n.allocated.memory, n.name))

    # ===================== Reserve + Bind =====================

    def _reserve_and_bind(self, pod: Pod, node: Node) -> None:
        self._reserve(pod, node)
        self._bind(pod, node)

    def _reserve(self, pod: Pod, node: Node) -> None:
        """Reserve 扩展点：预占资源，绑定失败会回滚（Reserve 有 Unreserve）。"""
        node.allocate(pod.total_request)
        node.pod_names.add(pod.name)

    def _bind(self, pod: Pod, node: Node) -> None:
        """Bind 扩展点（绑定周期）：把 nodeName 写回 apiserver，标记 PodScheduled。"""
        pod.node_name = node.name
        pod.conditions.add(Condition.POD_SCHEDULED)
        self.api.update_pod(pod)
        self.stats["scheduled"] += 1

    # ===================== PostFilter：抢占 =====================

    def _try_preempt(self, pod: Pod, req: Resources) -> Node | None:
        """找这样一个节点：驱逐其上所有优先级更低的 Pod 后，能放下 pod。

        真实 K8s 的 DefaultPreemption 更复杂（考虑拓扑、最小化驱逐数、PDB），
        这里简化为"可释放即可"。
        """
        victims_by_node: dict[str, list[Pod]] = {}
        for node in self.api.list_nodes():
            if not node.ready or not self._node_affinity(node, pod) or not self._taint_toleration(node, pod):
                continue
            lower = [
                other for other in self.api.list_pods()
                if other.node_name == node.name
                and other.priority.value < pod.priority.value
                and other.priority.preemptable
            ]
            released = Resources()
            for v in lower:
                released = released.add(v.total_request)
            if (node.allocatable.add(released)).fits(req):
                victims_by_node[node.name] = lower
        if not victims_by_node:
            return None
        # 选驱逐数最少、再选名字最小的节点（确定性）
        target_name = min(
            victims_by_node,
            key=lambda n: (len(victims_by_node[n]), n),
        )
        target = next(n for n in self.api.list_nodes() if n.name == target_name)
        for v in victims_by_node[target_name]:
            self._evict(v, target)
        return target

    def _evict(self, pod: Pod, node: Node) -> None:
        """驱逐：释放资源 + 删除 Pod（真实 K8s 会先 grace-period 再删）。"""
        node.release(pod.total_request)
        node.pod_names.discard(pod.name)
        self.api.delete_pod(pod.name)

    # ===================== Gang 查询（供测试）=====================
    def gang_status(self) -> dict[str, str]:
        pods = self.api.list_pods()
        gangs: dict[str, list[Pod]] = {}
        for p in pods:
            if p.is_gang:
                gangs.setdefault(p.gang_id, []).append(p)
        return {
            gid: f"{sum(1 for p in m if p.scheduled)}/{len(m)} scheduled"
            for gid, m in gangs.items()
        }
