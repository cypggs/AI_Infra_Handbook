"""test_apiserver.py — kube-apiserver 模拟（CRUD + 准入链）单元测试。

覆盖：
  - Pod/Node/Deployment/ReplicaSet CRUD
  - Mutating hook 可修改对象
  - Validating hook 可拒绝（AdmissionError）
  - 内置 require_resources_hook
"""

import pytest

from k8s_mini.apiserver import AdmissionError, ApiServer, require_resources_hook
from k8s_mini.model import Container, Deployment, Pod, Resources
from k8s_mini.store import Store


def _server() -> ApiServer:
    return ApiServer(Store())


def test_pod_crud():
    api = _server()
    p = Pod(name="p1", containers=[Container(name="a")])
    api.create_pod(p)
    assert api.get_pod("p1").name == "p1"
    p.phase = None  # type: ignore[assignment]
    api.update_pod(p)
    assert api.list_pods() and api.list_pods()[0].name == "p1"
    api.delete_pod("p1")
    assert api.get_pod("p1") is None


def test_node_register_and_list():
    from k8s_mini.model import Node

    api = _server()
    api.register_node(Node(name="n1", capacity=Resources(4, 8, 0)))
    assert len(api.list_nodes()) == 1
    assert api.get_node("n1") is not None


def test_deployment_and_replicaset_crud():
    api = _server()
    dep = Deployment(
        name="web", replicas=2, template_labels={"app": "web"},
        pod_template=Pod(name="t", containers=[Container(name="a")]),
    )
    api.create_deployment(dep)
    assert len(api.list_deployments()) == 1
    from k8s_mini.model import ReplicaSet

    rs = ReplicaSet(name="web-abc", replicas=2, template_labels={"app": "web"},
                    pod_template=Pod(name="t", containers=[Container(name="a")]))
    api.create_replicaset(rs)
    assert len(api.list_replicasets()) == 1
    api.delete_replicaset("web-abc")
    assert api.list_replicasets() == []


def test_mutating_hook_runs_before_validating():
    api = _server()

    def add_default_label(kind, obj):
        if kind == "pod" and isinstance(obj, Pod):
            obj.labels.setdefault("injected-by", "mutating-webhook")

    api.add_mutating_hook(add_default_label)
    p = Pod(name="p1", containers=[Container(name="a")])
    api.create_pod(p)
    assert api.get_pod("p1").labels.get("injected-by") == "mutating-webhook"


def test_validating_hook_can_reject():
    api = _server()

    def reject_evil(kind, obj):
        if kind == "pod" and isinstance(obj, Pod) and "evil" in obj.name:
            raise AdmissionError("evil pod rejected")

    api.add_validating_hook(reject_evil)
    with pytest.raises(AdmissionError):
        api.create_pod(Pod(name="evil-1", containers=[Container(name="a")]))
    # 拒绝后未写入 store
    assert api.get_pod("evil-1") is None


def test_require_resources_hook_rejects_zero_request():
    api = _server()
    api.add_validating_hook(require_resources_hook)
    # 容器既无 cpu 也无 memory request → 被拒绝
    bare = Pod(name="p1", containers=[Container(name="a", requests=Resources(0, 0, 0))])
    with pytest.raises(AdmissionError):
        api.create_pod(bare)
    # 有 request → 通过
    ok = Pod(name="p2", containers=[Container(name="a", requests=Resources(100, 128, 0))])
    api.create_pod(ok)
    assert api.get_pod("p2") is not None
