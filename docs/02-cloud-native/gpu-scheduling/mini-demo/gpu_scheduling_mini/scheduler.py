"""Scheduler —— 模拟 kube-scheduler + Scheduler Framework。

对应真实组件：
  - Filter / Score / Reserve / Bind 扩展点
  - NodeResourcesFit、NodeResourceTopology 等插件语义
  - 拓扑感知打分通过 TopologyScorer 注入

本模拟器省略了调度队列、并发、抢占、PreBind/PostBind 等复杂语义，
只保留"为一个 Pod 选出最优节点并绑定"的最小可复现路径。
"""
from . import model


class SchedulerError(Exception):
    pass


class Scheduler:
    """最小 GPU 感知调度器。

    支持的资源名：
      - nvidia.com/gpu          整卡
      - nvidia.com/mig-<profile> MIG 实例
      - nvidia.com/gpu.shared   共享切片（MPS/time-slicing 抽象）
    """

    def __init__(self, api, topology_scorer=None):
        self.api = api
        self.topology_scorer = topology_scorer

    def _node_by_name(self, name):
        """按名称查找节点（兼容 Nodes 在本模拟器中使用 default namespace 的设定）。"""
        for node in self.api.list(kind="Node").values():
            if node["metadata"]["name"] == name:
                return node
        return None

    # ------------------------------------------------------------------ #
    # Filter：硬性约束
    # ------------------------------------------------------------------ #
    def node_fits_pod(self, node, pod):
        """判断节点是否满足 Pod 的 GPU 资源请求。"""
        req = model.pod_resource_requests(pod)

        # 若 Pod 已绑定节点，只能落在该节点
        desired_node = pod["spec"].get("nodeName")
        if desired_node and node["metadata"]["name"] != desired_node:
            return False

        for resource_name, amount in req.requests.items():
            amount = int(amount)
            if amount == 0:
                continue
            if resource_name == model.GPU_RESOURCE:
                if model.node_free_gpus(node) < amount:
                    return False
            elif resource_name.startswith(model.MIG_RESOURCE_PREFIX):
                profile = resource_name[len(model.MIG_RESOURCE_PREFIX):]
                if model.node_free_mig(node, profile) < amount:
                    return False
            elif resource_name == model.GPU_SHARED_RESOURCE:
                if model.free_shared_gpu_slices(node) < amount:
                    return False
            # 其他资源（cpu/memory）本模拟器不建模，视为满足
        return True

    # ------------------------------------------------------------------ #
    # Score：软性偏好
    # ------------------------------------------------------------------ #
    def score_node(self, pod, node, indices):
        """给可行节点打分（0-100，越高越优）。"""
        req = model.pod_resource_requests(pod)
        gpu_count = req.requests.get(model.GPU_RESOURCE, 0)

        score = 0
        # 拓扑感知：整卡多卡训练优先 NUMA/PCIe/NVSwitch 紧凑
        if gpu_count > 0 and self.topology_scorer and node["status"].get("topology"):
            score += self.topology_scorer.score_indices(indices)
        else:
            score += 50

        # binpack：倾向把节点用满，减少碎片
        score += self._binpack_bonus(node, pod, indices)
        return min(100, score)

    def _binpack_bonus(self, node, pod, indices):
        """根据分配后资源占用比例给 0-20 的额外加分。"""
        req = model.pod_resource_requests(pod)
        bonus = 0

        whole = req.requests.get(model.GPU_RESOURCE, 0)
        if whole:
            cap = node["status"]["capacity"].get(model.GPU_RESOURCE, 0)
            if cap:
                free_before = model.node_free_gpus(node)
                free_after = free_before - whole
                alloc = cap - free_after
                bonus += int((alloc / cap) * 20)

        # MIG 与 shared 也按容量比例奖励，但权重较低
        for name, amount in req.requests.items():
            if name.startswith(model.MIG_RESOURCE_PREFIX):
                profile = name[len(model.MIG_RESOURCE_PREFIX):]
                cap = node["status"]["capacity"].get(name, 0)
                if cap:
                    free_before = model.node_free_mig(node, profile)
                    alloc = cap - (free_before - amount)
                    bonus += int((alloc / cap) * 10)
            elif name == model.GPU_SHARED_RESOURCE:
                cap = node["status"]["capacity"].get(model.GPU_RESOURCE, 0) * 10
                if cap:
                    free_before = model.free_shared_gpu_slices(node)
                    alloc = cap - (free_before - amount)
                    bonus += int((alloc / cap) * 10)

        return min(20, bonus)

    # ------------------------------------------------------------------ #
    # 设备选择（不修改状态）
    # ------------------------------------------------------------------ #
    def _pick_devices(self, node, pod):
        """为 Pod 在节点上选出推荐设备索引，返回 (indices, 资源类型)。

        不修改节点状态；真正的分配在 assign() 中完成。
        """
        req = model.pod_resource_requests(pod)

        # 整卡优先
        whole = req.requests.get(model.GPU_RESOURCE, 0)
        if whole:
            prefer = None
            if self.topology_scorer and node["status"].get("topology"):
                _, prefer = self.topology_scorer.best_indices(node, whole)
            indices = self._pick_by_profile(node, None, whole, prefer)
            if indices is None:
                return None, None
            return indices, model.GPU_RESOURCE

        # MIG
        for name, amount in req.requests.items():
            if name.startswith(model.MIG_RESOURCE_PREFIX):
                profile = name[len(model.MIG_RESOURCE_PREFIX):]
                indices = self._pick_by_profile(node, profile, amount)
                if indices is None:
                    return None, None
                return indices, name

        # 共享切片
        shared = req.requests.get(model.GPU_SHARED_RESOURCE, 0)
        if shared:
            if model.free_shared_gpu_slices(node) < shared:
                return None, None
            return [], model.GPU_SHARED_RESOURCE

        return [], None

    def _pick_by_profile(self, node, mig_profile, count, prefer_indices=None):
        """从节点中选出 count 个满足 profile 的健康未分配设备索引。"""
        devices = [
            d for d in node["status"]["devices"]
            if d.mig_profile == mig_profile
            and not d.allocated
            and d.health == "Healthy"
        ]
        if prefer_indices:
            order = {idx: i for i, idx in enumerate(prefer_indices)}
            devices.sort(key=lambda d: order.get(d.index, len(prefer_indices)))
        if len(devices) < count:
            return None
        return [d.index for d in devices[:count]]

    # ------------------------------------------------------------------ #
    # 调度主流程
    # ------------------------------------------------------------------ #
    def find_best_node(self, pod):
        """为 Pod 找到最优节点与设备索引。

        返回 (node_name, indices, resource_type, score)，若无可行节点返回 None。
        """
        nodes = self.api.list(kind="Node").values()
        candidates = []
        for node in nodes:
            if not self.node_fits_pod(node, pod):
                continue
            indices, rtype = self._pick_devices(node, pod)
            if indices is None and rtype is not None:
                continue
            score = self.score_node(pod, node, indices)
            candidates.append((score, node["metadata"]["name"], indices, rtype))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]
        return best[1], best[2], best[3], best[0]

    def schedule_one(self, pod):
        """为一个 Pod 执行完整调度：Filter → Score → Bind。"""
        result = self.find_best_node(pod)
        if result is None:
            return False
        node_name, indices, rtype, _ = result
        return self.assign(pod, node_name, indices, rtype)

    # ------------------------------------------------------------------ #
    # Bind / Unbind
    # ------------------------------------------------------------------ #
    def assign(self, pod, node_name, indices, resource_type):
        """把 Pod 绑定到节点并真正分配设备。"""
        node = self._node_by_name(node_name)
        if node is None:
            raise SchedulerError(f"node {node_name} not found")

        req = model.pod_resource_requests(pod)
        allocated = []
        try:
            if resource_type == model.GPU_RESOURCE:
                count = req.requests.get(model.GPU_RESOURCE, 0)
                chosen, err = model.allocate_gpus(node, count, prefer_indices=indices)
                if err:
                    return False
                allocated = chosen
            elif resource_type and resource_type.startswith(model.MIG_RESOURCE_PREFIX):
                profile = resource_type[len(model.MIG_RESOURCE_PREFIX):]
                count = req.requests.get(resource_type, 0)
                chosen, err = model.allocate_gpus(node, count, mig_profile=profile, prefer_indices=indices)
                if err:
                    return False
                allocated = chosen
            elif resource_type == model.GPU_SHARED_RESOURCE:
                count = req.requests.get(model.GPU_SHARED_RESOURCE, 0)
                ok, err = model.allocate_shared_slices(node, count)
                if not ok:
                    return False
        except Exception:
            model.release_gpus(node, allocated)
            raise

        # 持久化节点状态变更
        self.api.update_status(node)

        # 持久化 Pod 绑定
        pod["spec"]["nodeName"] = node_name
        pod["status"]["phase"] = "Scheduled"
        if resource_type == model.GPU_SHARED_RESOURCE:
            pod["status"]["allocated_devices"] = {resource_type: count}
        elif allocated:
            pod["status"]["allocated_devices"] = {resource_type: allocated}
        else:
            pod["status"]["allocated_devices"] = {}
        self.api.update(pod)
        return True

    def unbind(self, pod):
        """解除 Pod 的绑定并释放设备（用于 Gang 调度回滚或删除）。"""
        node_name = pod["spec"].get("nodeName")
        if not node_name:
            return False
        node = self._node_by_name(node_name)
        if node is None:
            return False

        allocated = pod["status"].get("allocated_devices", {})
        for rname, val in allocated.items():
            if rname == model.GPU_RESOURCE:
                model.release_gpus(node, val)
            elif rname == model.GPU_SHARED_RESOURCE:
                model.release_shared_slices(node, val)

        self.api.update_status(node)

        pod["spec"]["nodeName"] = ""
        pod["status"]["phase"] = "Pending"
        pod["status"]["allocated_devices"] = {}
        self.api.update(pod)
        return True
