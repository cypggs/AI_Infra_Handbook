"""资源模型 —— 用普通 dict 表达 K8s 资源：metadata / spec / status 三段式。

对应真实组件：
  - Node / Pod / PodGroup / Queue 是 K8s / Volcano 原生 API 资源
  - GPU 是本模拟器对 `nvidia.com/gpu` 设备对象的内部表示
  - Resources 对应 Pod.spec.containers[*].resources.requests/limits
"""
import copy


# --------------------------------------------------------------------------- #
# 资源 kind 常量
# --------------------------------------------------------------------------- #
NODE_KIND = "Node"
POD_KIND = "Pod"
POD_GROUP_KIND = "PodGroup"
QUEUE_KIND = "Queue"

# 真实 K8s 资源名
GPU_RESOURCE = "nvidia.com/gpu"

# MIG profile 命名前缀：nvidia.com/mig-1g.5gb、nvidia.com/mig-2g.10gb 等
MIG_RESOURCE_PREFIX = "nvidia.com/mig-"

# GPU 共享：MPS / time-slicing 用一个虚拟扩展资源表示共享 GPU 切片
GPU_SHARED_RESOURCE = "nvidia.com/gpu.shared"


# --------------------------------------------------------------------------- #
# Resources 语义封装
# --------------------------------------------------------------------------- #
class Resources:
    """对应 K8s ResourceRequirements；只保留 requests/limits 的计数语义。"""

    def __init__(self, requests=None, limits=None):
        self.requests = dict(requests or {})
        self.limits = dict(limits or {})

    @classmethod
    def from_container(cls, container):
        """从 container.resources 解析。"""
        res = container.get("resources") or {}
        return cls(res.get("requests") or {}, res.get("limits") or {})

    @classmethod
    def sum_containers(cls, containers):
        """汇总 Pod 中所有容器的资源需求。"""
        total = cls()
        for c in containers or []:
            r = cls.from_container(c)
            total.add(r)
        return total

    def add(self, other):
        for k, v in other.requests.items():
            self.requests[k] = self.requests.get(k, 0) + v
        for k, v in other.limits.items():
            self.limits[k] = self.limits.get(k, 0) + v

    def get(self, name, default=0):
        return self.requests.get(name, default)

    def __contains__(self, name):
        return name in self.requests or name in self.limits

    def __repr__(self):
        return f"Resources(requests={self.requests}, limits={self.limits})"


# --------------------------------------------------------------------------- #
# GPU 设备对象
# --------------------------------------------------------------------------- #
class GPU:
    """单个 GPU 设备（或 MIG 实例）的内部表示。"""

    def __init__(self, index, uuid=None, health="Healthy", mig_profile=None):
        self.index = int(index)
        self.uuid = uuid or f"GPU-{index:04x}"
        self.health = health  # "Healthy" | "Unhealthy"
        self.mig_profile = mig_profile  # None 表示整卡；否则为 "1g.5gb" 等
        self.allocated = False

    def __repr__(self):
        base = f"GPU({self.index}, uuid={self.uuid}, health={self.health}"
        if self.mig_profile:
            base += f", mig={self.mig_profile}"
        return base + ")"


# --------------------------------------------------------------------------- #
# 构造函数
# --------------------------------------------------------------------------- #
def _meta(name, namespace="default", **extra):
    m = {
        "name": name,
        "namespace": namespace,
        "resourceVersion": "0",
        "generation": 1,
        "labels": {},
        "annotations": {},
        "deletionTimestamp": None,
    }
    m.update(extra)
    return m


def make_node(name, *, gpu_count=0, mig_devices=None, labels=None, topology=None):
    """构造 Node 对象。

    gpu_count: 整卡 GPU 数量
    mig_devices: {profile: count}，例如 {"1g.5gb": 7}，用于生成 MIG 实例设备
    topology: Topology 对象，描述 NUMA / PCIe / NVSwitch 拓扑
    """
    devices = []
    for i in range(gpu_count):
        devices.append(GPU(i, mig_profile=None))
    mig_devices = mig_devices or {}
    counter = gpu_count
    for profile, count in mig_devices.items():
        for _ in range(count):
            devices.append(GPU(counter, mig_profile=profile))
            counter += 1

    allocatable = {GPU_RESOURCE: gpu_count}
    for profile, count in mig_devices.items():
        allocatable[f"{MIG_RESOURCE_PREFIX}{profile}"] = count

    return {
        "apiVersion": "v1",
        "kind": NODE_KIND,
        "metadata": _meta(name, labels=labels or {}),
        "spec": {},
        "status": {
            "allocatable": allocatable,
            "capacity": dict(allocatable),
            "devices": devices,
            "topology": topology,
        },
    }


def make_pod(name, namespace="default", *, node_name="", containers=None,
             labels=None, annotations=None, pod_group_name=""):
    """构造 Pod 对象。

    containers 示例：[{"name": "train", "resources": {"requests": {"nvidia.com/gpu": 2}}}]
    """
    return {
        "apiVersion": "v1",
        "kind": POD_KIND,
        "metadata": _meta(name, namespace, labels=labels or {}, annotations=annotations or {}),
        "spec": {
            "nodeName": node_name,
            "containers": containers or [],
            "podGroupName": pod_group_name,
        },
        "status": {
            "phase": "Pending",
            "allocated_devices": {},  # {container_name: [gpu_index, ...]}
        },
    }


def make_podgroup(name, namespace="default", *, min_member=1, queue_name="default"):
    """构造 Volcano 风格 PodGroup 对象。"""
    return {
        "apiVersion": "scheduling.volcano.sh/v1beta1",
        "kind": POD_GROUP_KIND,
        "metadata": _meta(name, namespace),
        "spec": {
            "minMember": min_member,
            "queue": queue_name,
        },
        "status": {
            "phase": "Pending",
            "running": 0,
            "succeeded": 0,
        },
    }


def make_queue(name, *, weight=1):
    """构造 Volcano Queue 对象。"""
    return {
        "apiVersion": "scheduling.volcano.sh/v1beta1",
        "kind": QUEUE_KIND,
        "metadata": _meta(name, namespace=""),
        "spec": {"weight": weight},
        "status": {"pending": 0, "running": 0},
    }


# --------------------------------------------------------------------------- #
# 语义辅助函数
# --------------------------------------------------------------------------- #
def key(obj):
    """资源全局唯一键 (kind, namespace, name)。"""
    md = obj["metadata"]
    return (obj["kind"], md.get("namespace", ""), md["name"])


def pod_resource_requests(pod):
    """返回 Pod 所有容器资源请求的 Resources 对象。"""
    return Resources.sum_containers(pod["spec"].get("containers"))


def gpu_request_count(pod):
    """返回 Pod 请求的 nvidia.com/gpu 整卡数量。"""
    return pod_resource_requests(pod).get(GPU_RESOURCE, 0)


def mig_request_counts(pod):
    """返回 Pod 请求的 MIG profile -> count 映射。"""
    counts = {}
    req = pod_resource_requests(pod)
    for name, amount in req.requests.items():
        if name.startswith(MIG_RESOURCE_PREFIX):
            profile = name[len(MIG_RESOURCE_PREFIX):]
            counts[profile] = counts.get(profile, 0) + int(amount)
    return counts


def shared_gpu_request_count(pod):
    """返回 Pod 请求的共享 GPU 切片数量。"""
    return pod_resource_requests(pod).get(GPU_SHARED_RESOURCE, 0)


def node_free_gpus(node):
    """返回节点上未被分配且健康的整卡 GPU 数量。"""
    return sum(
        1 for d in node["status"]["devices"]
        if d.mig_profile is None and not d.allocated and d.health == "Healthy"
    )


def node_free_mig(node, profile):
    """返回节点上指定 profile 且未被分配、健康的 MIG 实例数量。"""
    return sum(
        1 for d in node["status"]["devices"]
        if d.mig_profile == profile and not d.allocated and d.health == "Healthy"
    )


def free_shared_gpu_slices(node):
    """返回节点上可用于共享的整卡 GPU 切片容量。

    简化：每张整卡最多承载 10 个共享切片。
    """
    whole = node_free_gpus(node)
    return whole * 10 - node["status"].get("shared_allocated", 0)


def allocate_shared_slices(node, count):
    """在节点上分配 count 个共享 GPU 切片（MPS/time-slicing 的抽象）。"""
    free = free_shared_gpu_slices(node)
    if count > free:
        return False, f"insufficient shared slices: want {count}, have {free}"
    node["status"]["shared_allocated"] = node["status"].get("shared_allocated", 0) + count
    return True, ""


def release_shared_slices(node, count):
    """释放 count 个共享 GPU 切片。"""
    cur = node["status"].get("shared_allocated", 0)
    node["status"]["shared_allocated"] = max(0, cur - count)


def allocate_gpus(node, count, *, mig_profile=None, prefer_indices=None):
    """在节点上分配 count 个 GPU，返回 (gpu_indices, error_message)。

    prefer_indices: 优先使用的设备索引列表（拓扑打分后使用）
    """
    devices = node["status"]["devices"]
    candidates = [
        d for d in devices
        if d.mig_profile == mig_profile
        and not d.allocated
        and d.health == "Healthy"
    ]
    if prefer_indices:
        order = {idx: i for i, idx in enumerate(prefer_indices)}
        candidates.sort(key=lambda d: order.get(d.index, len(prefer_indices)))
    if len(candidates) < count:
        kind = f"MIG {mig_profile}" if mig_profile else "whole GPU"
        return [], f"insufficient {kind}: want {count}, have {len(candidates)}"
    chosen = candidates[:count]
    for d in chosen:
        d.allocated = True
    return [d.index for d in chosen], ""


def release_gpus(node, indices):
    """释放节点上指定索引的 GPU / MIG 实例。"""
    by_index = {d.index: d for d in node["status"]["devices"]}
    for idx in indices:
        d = by_index.get(idx)
        if d:
            d.allocated = False


def is_scheduled(pod):
    return bool(pod["spec"].get("nodeName"))


def deep_copy(obj):
    return copy.deepcopy(obj)
