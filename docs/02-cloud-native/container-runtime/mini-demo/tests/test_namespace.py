"""test_namespace — 隔离与 Pod 共享。"""
from crt_mini.namespace import NamespaceSet, Namespace


def test_isolated_set_has_all_types():
    ns = NamespaceSet.isolated()
    assert set(ns.isolated_types()) == {"pid", "net", "mnt", "uts", "ipc", "user"}
    assert isinstance(ns.pid, Namespace)


def test_two_containers_have_distinct_namespaces():
    a = NamespaceSet.isolated()
    b = NamespaceSet.isolated()
    assert a.uts is not b.uts
    assert a.net is not b.net
    a.uts.add("host-a")
    b.uts.add("host-b")
    assert a.uts.visible() == ["host-a"]
    assert b.uts.visible() == ["host-b"]


def test_shared_with_joins_net_ipc_for_pod_members():
    sandbox = NamespaceSet.isolated()  # 模拟 pause 容器持有 Pod namespace
    member = NamespaceSet.isolated()
    member.shared_with(sandbox, types=("net", "ipc"))
    assert member.net is sandbox.net    # Pod 内容器共享网络栈
    assert member.ipc is sandbox.ipc
    assert member.uts is not sandbox.uts  # 但 uts 仍各自独立
