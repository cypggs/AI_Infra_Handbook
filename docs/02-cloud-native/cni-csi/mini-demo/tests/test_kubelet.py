"""kubelet 测试：Pod 网络/存储收敛、删除清理、watch 触发、乐观锁重试。"""
import pytest

from cni_csi_mini import (
    FakeApiServer, FakeClock,
    make_node, make_pod, make_pvc,
    volume_mount, container_mount,
    BridgePlugin, PluginChain, RouteManager,
    VolumeStore, NodeVolumeStore, ControllerServer, NodeServer,
    Kubelet,
)


def make_fixture(node_name="node-1", cidr="10.244.1.0/24"):
    clock = FakeClock(0.0)
    api = FakeApiServer()
    routes = RouteManager()
    bridge = BridgePlugin(routes=routes)
    cni_plugin = PluginChain([bridge])
    store = VolumeStore()
    ctrl = ControllerServer(store)

    node = make_node(node_name, cidr=cidr)
    api.create(node)
    routes.register_node(node_name, node["status"]["addresses"][0]["address"], cidr)
    node_store = NodeVolumeStore(node_name)
    kubelet = Kubelet(node_name, api, cni_plugin, ctrl, node_store, routes, clock)
    return api, kubelet, bridge, store, node_store


def test_pod_creation_gets_ip_and_mount():
    api, kubelet, bridge, store, node_store = make_fixture()
    pvc = make_pvc("data", size_gi=1)
    api.create(pvc)
    pod = make_pod("app", node_name="node-1", volumes=[volume_mount("data", "/data")],
                   containers=[{"name": "main", "image": "busybox",
                                "volumeMounts": [container_mount("vol-data", "/data")]}])
    api.create(pod)
    kubelet.sync_pod(pod)

    final = api.get("Pod", "default", "app")
    assert final["status"]["podIP"].startswith("10.244.1")
    assert final["status"]["phase"] == "Running"
    pvc_final = api.get("PersistentVolumeClaim", "default", "data")
    assert pvc_final["status"]["phase"] == "Bound"
    pv = api.get("PersistentVolume", "", "pv-data")
    vol_id = pv["spec"]["csi"]["volumeHandle"]
    assert node_store.is_staged(vol_id)
    assert node_store.is_published_to_pod(vol_id, "sandbox-node-1-app")


def test_pod_deletion_cleans_up():
    api, kubelet, bridge, store, node_store = make_fixture()
    pvc = make_pvc("data", size_gi=1)
    api.create(pvc)
    pod = make_pod("app", node_name="node-1", volumes=[volume_mount("data", "/data")],
                   containers=[{"name": "main", "image": "busybox",
                                "volumeMounts": [container_mount("vol-data", "/data")]}])
    api.create(pod)
    kubelet.sync_pod(pod)

    final = api.get("Pod", "default", "app")
    kubelet.delete_pod(final)

    pv = api.get("PersistentVolume", "", "pv-data")
    vol_id = pv["spec"]["csi"]["volumeHandle"]
    assert not node_store.is_published_to_pod(vol_id, "sandbox-node-1-app")
    assert not node_store.is_staged(vol_id)
    assert not store.is_attached_to(vol_id, "node-1")
    na = api.get("NetworkAttachment", "default", "sandbox-node-1-app")
    assert na is None


def test_watch_triggers_sync():
    api, kubelet, bridge, store, node_store = make_fixture()
    pod = make_pod("app", node_name="node-1")
    api.create(pod)
    idx = api.event_index()
    api.create(make_pod("trigger", node_name="node-1"))
    events = api.events_since(idx)
    assert len(events) == 1
    # kubelet 可以基于事件列表触发 syncPod（本测试验证事件流语义）
    kubelet.sync_pod(events[0]["object"])
    assert api.get("Pod", "default", "trigger")["status"]["podIP"] != ""


def test_optimistic_lock_retry():
    api, kubelet, bridge, store, node_store = make_fixture()
    pod = make_pod("app", node_name="node-1")
    api.create(pod)
    api.inject_conflict(2)
    kubelet.sync_pod(pod)
    final = api.get("Pod", "default", "app")
    assert final["status"]["phase"] == "Running"


def test_read_only_mount_respected():
    api, kubelet, bridge, store, node_store = make_fixture()
    pvc = make_pvc("data", size_gi=1, access_modes=["ReadOnlyMany"])
    api.create(pvc)
    pod = make_pod("app", node_name="node-1",
                   volumes=[volume_mount("data", "/data", read_only=True)],
                   containers=[{"name": "main", "image": "busybox",
                                "volumeMounts": [container_mount("vol-data", "/data", read_only=True)]}])
    api.create(pod)
    kubelet.sync_pod(pod)
    pv = api.get("PersistentVolume", "", "pv-data")
    vol_id = pv["spec"]["csi"]["volumeHandle"]
    va = store.get_attachment(vol_id, "node-1")
    assert va["spec"]["readOnly"] is True
    pub = node_store._published[vol_id]["sandbox-node-1-app"]
    assert pub["read_only"] is True
