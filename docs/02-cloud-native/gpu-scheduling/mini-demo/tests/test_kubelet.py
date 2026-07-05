"""kubelet.py 测试。"""
import pytest

from gpu_scheduling_mini.kubelet import Kubelet, KubeletError
from gpu_scheduling_mini.device_plugin import DevicePlugin
from gpu_scheduling_mini.apiserver import FakeApiServer
from gpu_scheduling_mini import model


def _setup(gpu_count=2):
    api = FakeApiServer()
    node = model.make_node("node-1", gpu_count=gpu_count)
    api.create(node)
    kubelet = Kubelet(api, "node-1")
    plugin = DevicePlugin(model.GPU_RESOURCE, node["status"]["devices"])
    plugin.register(kubelet)
    return api, kubelet, node


def test_sync_pod_allocates_gpu_and_injects_env():
    api, kubelet, _ = _setup()
    pod = model.make_pod("train", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 1}},
    }])
    pod["spec"]["nodeName"] = "node-1"
    api.create(pod)

    allocs = kubelet.sync_pod(pod)
    assert allocs == {"train": [0]}
    env = {e["name"]: e["value"] for e in pod["spec"]["containers"][0]["env"]}
    assert "NVIDIA_VISIBLE_DEVICES" in env
    assert pod["status"]["phase"] == "Running"


def test_sync_pod_not_enough_devices():
    api, kubelet, _ = _setup(gpu_count=1)
    pod = model.make_pod("train", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 2}},
    }])
    pod["spec"]["nodeName"] = "node-1"
    api.create(pod)
    with pytest.raises(KubeletError):
        kubelet.sync_pod(pod)


def test_delete_pod_releases_devices():
    api, kubelet, _ = _setup()
    pod = model.make_pod("train", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 1}},
    }])
    pod["spec"]["nodeName"] = "node-1"
    api.create(pod)
    kubelet.sync_pod(pod)
    assert kubelet.allocated_count(model.GPU_RESOURCE) == 1

    kubelet.delete_pod(pod)
    assert kubelet.allocated_count(model.GPU_RESOURCE) == 0
    assert pod["status"]["phase"] == "Succeeded"


def test_sync_pod_wrong_node_rejected():
    api, kubelet, _ = _setup()
    pod = model.make_pod("train", containers=[{
        "name": "train",
        "resources": {"requests": {model.GPU_RESOURCE: 1}},
    }])
    pod["spec"]["nodeName"] = "node-2"
    api.create(pod)
    with pytest.raises(KubeletError):
        kubelet.sync_pod(pod)


def test_sync_pod_skips_unknown_resource():
    api, kubelet, _ = _setup()
    pod = model.make_pod("train", containers=[{
        "name": "train",
        "resources": {"requests": {"vendor.com/foo": 1}},
    }])
    pod["spec"]["nodeName"] = "node-1"
    api.create(pod)
    allocs = kubelet.sync_pod(pod)
    assert allocs == {}
