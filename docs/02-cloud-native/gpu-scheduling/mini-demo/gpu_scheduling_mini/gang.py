"""GangScheduler —— 模拟 Volcano / Coscheduling 的 PodGroup all-or-nothing 调度。

对应真实组件：
  - Volcano 的 PodGroup + Queue 语义
  - scheduler-plugins Coscheduling 的 Reserve / Permit 阶段

核心思想：一个 PodGroup 的 minMember 必须同时被调度，否则一个都不调，
避免分布式训练/推理出现"部分 Pod 占用资源、剩余 Pod 永远 Pending"的死锁。
"""
from . import model
from .scheduler import SchedulerError


class PodGroupState:
    Pending = "Pending"
    Scheduling = "Scheduling"
    Scheduled = "Scheduled"
    Failed = "Failed"


class GangScheduler:
    """基于 PodGroup 的 Gang 调度器。

    它复用普通 Scheduler 的 Filter/Score，但在绑定阶段采用"先检查、后提交"的两阶段提交，
    保证 all-or-nothing。
    """

    def __init__(self, api, scheduler):
        self.api = api
        self.scheduler = scheduler

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def pods_for_group(self, pod_group):
        """返回属于该 PodGroup 且未绑定节点的所有 Pod。"""
        pg_key = model.key(pod_group)
        namespace = pod_group["metadata"]["namespace"]
        all_pods = self.api.list(kind="Pod", namespace=namespace).values()
        return [
            p for p in all_pods
            if p["spec"].get("podGroupName") == pod_group["metadata"]["name"]
            and not p["spec"].get("nodeName")
        ]

    # ------------------------------------------------------------------ #
    # 两阶段提交
    # ------------------------------------------------------------------ #
    def schedule_group(self, pod_group):
        """尝试调度一个 PodGroup。

        采用"逐个检查并提交，失败则全部回滚"的两阶段提交，保证 all-or-nothing。
        返回 (success, message)。
        """
        pods = self.pods_for_group(pod_group)
        min_member = pod_group["spec"].get("minMember", 1)

        if len(pods) < min_member:
            return False, f"pods {len(pods)} < minMember {min_member}"

        committed = []
        try:
            for pod in pods:
                result = self.scheduler.find_best_node(pod)
                if result is None:
                    self._rollback(committed)
                    self._set_pg_phase(pod_group, PodGroupState.Pending)
                    return False, f"pod {pod['metadata']['name']} has no feasible node"
                node_name, indices, rtype, _ = result
                ok = self.scheduler.assign(pod, node_name, indices, rtype)
                if not ok:
                    self._rollback(committed)
                    self._set_pg_phase(pod_group, PodGroupState.Pending)
                    return False, f"assign failed for pod {pod['metadata']['name']}"
                committed.append(pod)
        except Exception:
            self._rollback(committed)
            raise

        self._set_pg_phase(pod_group, PodGroupState.Scheduled)
        return True, f"scheduled {len(committed)} pods"

    def _rollback(self, committed):
        """回滚已提交的 Pod。"""
        for pod in committed:
            self.scheduler.unbind(pod)

    def _set_pg_phase(self, pod_group, phase):
        """更新 PodGroup 状态，并同步返回的最新 resourceVersion。"""
        pod_group["status"]["phase"] = phase
        pod_group["status"]["running"] = len([
            p for p in self.pods_for_group(pod_group)
            if p["status"].get("phase") == "Scheduled"
        ])
        updated = self.api.update_status(pod_group)
        pod_group["metadata"]["resourceVersion"] = updated["metadata"]["resourceVersion"]
        return pod_group

    # ------------------------------------------------------------------ #
    # 批量调度
    # ------------------------------------------------------------------ #
    def schedule_all(self):
        """遍历所有 Pending PodGroup，逐个尝试 Gang 调度。"""
        groups = self.api.list(kind="PodGroup").values()
        results = []
        for pg in groups:
            if pg["status"].get("phase") == PodGroupState.Scheduled:
                continue
            ok, msg = self.schedule_group(pg)
            results.append((pg["metadata"]["name"], ok, msg))
        return results
