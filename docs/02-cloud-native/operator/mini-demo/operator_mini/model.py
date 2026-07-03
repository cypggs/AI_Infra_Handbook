"""CRD 资源模型 —— 把 InferenceService / Deployment / Service 表示为普通 dict。

和真实 K8s 一样，资源是 JSON 形态的对象：metadata / spec / status 三段。
apiserver 对所有 kind 一视同仁（按 (kind, namespace, name) 存取），所以这里只提供
"构造函数"和"语义辅助函数"，不引入强类型 —— 这正是 K8s API 的设计。
"""
import copy

GROUP = "inference.io"
VERSION = "v1"
INFERENCE_SERVICE_KIND = "InferenceService"
DEPLOYMENT_KIND = "Deployment"
SERVICE_KIND = "Service"

# 推理服务的 finalizer：删除前用它挂钩"清理外部资源"（注销云 LB 等）。
FINALIZER = "inference.io/finalizer"


# --------------------------------------------------------------------------- #
# 构造函数
# --------------------------------------------------------------------------- #
def _meta(name, namespace="default", **extra):
    m = {
        "name": name,
        "namespace": namespace,
        "resourceVersion": "0",   # apiserver 在写入时分配真正的值
        "generation": 1,          # spec 每次变更 +1；status 变更不递增
        "finalizers": [],
        "deletionTimestamp": None,
        "ownerReferences": [],
    }
    m.update(extra)
    return m


def make_inference_service(name, namespace="default", *, image, replicas, model):
    """构造一个 InferenceService CR（用户写的期望状态）。"""
    return {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": INFERENCE_SERVICE_KIND,
        "metadata": _meta(name, namespace),
        "spec": {"image": image, "replicas": int(replicas), "model": model},
        "status": {
            "observedGeneration": 0,
            "ready": False,
            "readyReplicas": 0,
            "conditions": [],
        },
    }


def make_deployment(name, namespace="default", *, image, replicas, labels):
    """构造 Operator 要保证存在的 Deployment（子资源）。"""
    return {
        "apiVersion": "apps/v1",
        "kind": DEPLOYMENT_KIND,
        "metadata": _meta(name, namespace, labels=labels),
        "spec": {"replicas": int(replicas), "image": image},
        "status": {"readyReplicas": 0},
    }


def make_service(name, namespace="default", *, port, selector, labels):
    """构造 Operator 要保证存在的 Service（子资源）。"""
    return {
        "apiVersion": "v1",
        "kind": SERVICE_KIND,
        "metadata": _meta(name, namespace, labels=labels),
        "spec": {"type": "ClusterIP", "port": port, "selector": selector},
        "status": {},
    }


# --------------------------------------------------------------------------- #
# 语义辅助函数
# --------------------------------------------------------------------------- #
def key(obj):
    """资源的全局唯一键：(kind, namespace, name)。workqueue 里存的就是它（去重粒度）。"""
    md = obj["metadata"]
    return (obj["kind"], md["namespace"], md["name"])


def is_being_deleted(obj):
    """deletionTimestamp 不为 None 表示该对象处于"删除中"（有 finalizer 时还没真删）。"""
    return obj["metadata"].get("deletionTimestamp") is not None


def has_finalizer(obj, finalizer=FINALIZER):
    return finalizer in obj["metadata"].get("finalizers", [])


def add_finalizer(obj, finalizer=FINALIZER):
    fl = obj["metadata"].setdefault("finalizers", [])
    if finalizer not in fl:
        fl.append(finalizer)


def remove_finalizer(obj, finalizer=FINALIZER):
    fl = obj["metadata"].get("finalizers", [])
    obj["metadata"]["finalizers"] = [f for f in fl if f != finalizer]


def set_owner_reference(child, owner):
    """把 child 的 controller owner 设为 owner —— CR 删了 child 自动级联回收（GC）。"""
    ref = {
        "controller": True,
        "kind": owner["kind"],
        "name": owner["metadata"]["name"],
        "namespace": owner["metadata"]["namespace"],
    }
    refs = child["metadata"].setdefault("ownerReferences", [])
    # 同 kind 只保留一个 controller 引用
    refs = [r for r in refs if not (r.get("kind") == ref["kind"] and r.get("controller"))]
    refs.append(ref)
    child["metadata"]["ownerReferences"] = refs


def controller_owner(obj):
    """返回 obj 的 controller owner 引用（dict），没有则 None。"""
    for r in obj["metadata"].get("ownerReferences", []):
        if r.get("controller"):
            return r
    return None


def controller_owner_id(obj):
    """controller owner 的 (kind, namespace, name)，用于级联 GC 查找。"""
    owner = controller_owner(obj)
    if owner is None:
        return None
    return (owner["kind"], owner["namespace"], owner["name"])


def deep_copy(obj):
    return copy.deepcopy(obj)
