"""资源模型 —— 用普通 dict 表达 K8s 资源：metadata / spec / status 三段式。

对应真实组件：
  - Pod / Node / PVC / PV / VolumeAttachment 是 K8s 原生 API 资源
  - NetworkAttachment 是 CNI 执行结果在本模拟器里的"持久化视图"
  - Volume 是 CSI 侧的内部对象（对应 K8s 里的 PV 底层实体，或 CSI CreateVolume 返回的 volume）
"""
import copy


# --------------------------------------------------------------------------- #
# 资源 kind 常量
# --------------------------------------------------------------------------- #
POD_KIND = "Pod"
NODE_KIND = "Node"
PVC_KIND = "PersistentVolumeClaim"
PV_KIND = "PersistentVolume"
VOLUME_ATTACHMENT_KIND = "VolumeAttachment"
NETWORK_ATTACHMENT_KIND = "NetworkAttachment"
VOLUME_KIND = "Volume"  # CSI 内部 volume 对象（非 K8s API 原生 kind）


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


def make_node(name, *, cidr="10.244.0.0/24", labels=None):
    """构造 Node 对象。cidr 是该节点 PodCIDR，由 IPAM 切分使用。"""
    return {
        "apiVersion": "v1",
        "kind": NODE_KIND,
        "metadata": _meta(name, labels=labels or {}),
        "spec": {"podCIDR": cidr},
        "status": {"addresses": [{"type": "InternalIP", "address": f"192.168.0.{name[-1]}"}]},
    }


def make_pod(name, namespace="default", *, node_name="", labels=None,
             volumes=None, containers=None):
    """构造 Pod 对象。volumes 声明要挂载的 PVC/emptyDir/configMap 等。"""
    return {
        "apiVersion": "v1",
        "kind": POD_KIND,
        "metadata": _meta(name, namespace, labels=labels or {}),
        "spec": {
            "nodeName": node_name,
            "volumes": volumes or [],
            "containers": containers or [{"name": "main", "image": "busybox"}],
        },
        "status": {
            "phase": "Pending",
            "podIP": "",
            "conditions": [],
        },
    }


def volume_mount(pvc_name, mount_path, read_only=False):
    """构造 Pod.spec.volumes 里的一项（PVC 类型）。"""
    return {
        "name": f"vol-{pvc_name}",
        "persistentVolumeClaim": {"claimName": pvc_name, "readOnly": read_only},
    }


def container_mount(name, mount_path, read_only=False):
    """构造 container.volumeMounts 里的一项。"""
    return {"name": name, "mountPath": mount_path, "readOnly": read_only}


def make_pvc(name, namespace="default", *, storage_class="standard",
             access_modes=None, size_gi=1):
    """构造 PersistentVolumeClaim。"""
    return {
        "apiVersion": "v1",
        "kind": PVC_KIND,
        "metadata": _meta(name, namespace),
        "spec": {
            "storageClassName": storage_class,
            "accessModes": access_modes or ["ReadWriteOnce"],
            "resources": {"requests": {"storage": f"{size_gi}Gi"}},
        },
        "status": {"phase": "Pending", "bound_pv": ""},
    }


def make_pv(name, *, capacity_gi=1, access_modes=None,
            storage_class="standard", volume_handle="", csi_driver="fake.csi"):
    """构造 PersistentVolume（对应 CSI 侧已 provision 的 volume）。PV 是集群作用域资源。"""
    return {
        "apiVersion": "v1",
        "kind": PV_KIND,
        "metadata": _meta(name, namespace=""),
        "spec": {
            "capacity": {"storage": f"{capacity_gi}Gi"},
            "accessModes": access_modes or ["ReadWriteOnce"],
            "storageClassName": storage_class,
            "csi": {"driver": csi_driver, "volumeHandle": volume_handle},
            "claimRef": None,
        },
        "status": {"phase": "Available"},
    }


def make_volume(name, *, size_gi=1, access_modes=None):
    """CSI 内部 volume 对象（CreateVolume 返回）。与 PV 1:1。"""
    return {
        "apiVersion": "csi.storage.k8s.io/v1",
        "kind": VOLUME_KIND,
        "metadata": _meta(name),
        "spec": {
            "sizeGi": size_gi,
            "accessModes": access_modes or ["ReadWriteOnce"],
        },
        "status": {"attached_to": None, "staged_on": set(), "published_on": {}},
    }


def make_volume_attachment(name, *, pv_name, node_name, attached=False):
    """构造 VolumeAttachment（CSI ControllerPublishVolume 的产物）。"""
    return {
        "apiVersion": "storage.k8s.io/v1",
        "kind": VOLUME_ATTACHMENT_KIND,
        "metadata": _meta(name),
        "spec": {
            "attacher": "fake.csi",
            "nodeName": node_name,
            "source": {"persistentVolumeName": pv_name},
        },
        "status": {"attached": attached},
    }


def make_network_attachment(pod_name, namespace="default", *, node_name, pod_ip,
                            sandbox_id, routes=None, dns=None):
    """CNI ADD 后保留在 apiserver（或本模拟器 store）里的网络连接状态。"""
    return {
        "apiVersion": "networking.io/v1",
        "kind": NETWORK_ATTACHMENT_KIND,
        "metadata": _meta(f"{pod_name}-{sandbox_id}", namespace),
        "spec": {
            "podName": pod_name,
            "namespace": namespace,
            "nodeName": node_name,
            "sandboxId": sandbox_id,
        },
        "status": {
            "podIP": pod_ip,
            "routes": routes or [],
            "dns": dns or {},
        },
    }


# --------------------------------------------------------------------------- #
# 语义辅助函数
# --------------------------------------------------------------------------- #
def key(obj):
    """资源全局唯一键 (kind, namespace, name)。"""
    md = obj["metadata"]
    return (obj["kind"], md.get("namespace", ""), md["name"])


def deep_copy(obj):
    return copy.deepcopy(obj)


def is_scheduled(pod):
    return bool(pod["spec"].get("nodeName"))


def pod_volumes(pod):
    """返回 Pod 声明的所有 PVC volume 名 -> claimName 映射。"""
    out = {}
    for vol in pod["spec"].get("volumes", []):
        pvc = vol.get("persistentVolumeClaim")
        if pvc:
            out[vol["name"]] = pvc["claimName"]
    return out


def access_mode_set(obj):
    """返回对象 spec.accessModes 的集合（兼容 PVC / PV / Volume）。"""
    modes = obj["spec"].get("accessModes") or []
    return set(modes)


def is_rwo(obj):
    return access_mode_set(obj) == {"ReadWriteOnce"}


def is_rox(obj):
    return "ReadOnlyMany" in access_mode_set(obj)


def is_rwx(obj):
    return "ReadWriteMany" in access_mode_set(obj)
