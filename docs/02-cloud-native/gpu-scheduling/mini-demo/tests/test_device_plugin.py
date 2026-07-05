"""device_plugin.py 测试。"""
import pytest

from gpu_scheduling_mini.device_plugin import DevicePlugin, DevicePluginError
from gpu_scheduling_mini import model
from gpu_scheduling_mini.clock import FakeClock


def _plugin(devices):
    return DevicePlugin(model.GPU_RESOURCE, devices, clock=FakeClock())


def test_register_and_list_and_watch():
    gpu = model.GPU(0)
    p = _plugin([gpu])
    assert not p.registered
    # register 需要 kubelet；这里用一个 mock 对象验证回调
    class MockKubelet:
        def register_plugin(self, plugin):
            self.plugin = plugin
    kl = MockKubelet()
    p.register(kl)
    assert p.registered
    assert kl.plugin is p
    devs = p.list_and_watch()
    assert devs[0]["id"] == "0"


def test_allocate_happy_path():
    gpus = [model.GPU(0), model.GPU(1)]
    p = _plugin(gpus)
    resp = p.allocate([0])
    assert "NVIDIA_VISIBLE_DEVICES" in resp["envs"]
    assert p.allocated_count() == 1


def test_allocate_duplicate_rejected():
    p = _plugin([model.GPU(0), model.GPU(1)])
    p.allocate([0])
    with pytest.raises(DevicePluginError):
        p.allocate([0])


def test_allocate_unhealthy_rejected():
    gpu = model.GPU(0)
    p = _plugin([gpu])
    p.health_check(0, False)
    with pytest.raises(DevicePluginError):
        p.allocate([0])


def test_health_check_callback():
    gpu = model.GPU(0)
    p = _plugin([gpu])
    events = []
    p.on_health_change(lambda r, i, h: events.append((r, i, h)))
    p.health_check(0, False)
    assert events == [(model.GPU_RESOURCE, 0, "Unhealthy")]


def test_release():
    p = _plugin([model.GPU(0), model.GPU(1)])
    p.allocate([0, 1])
    p.release([0])
    assert p.allocated_count() == 1
    assert 0 in p.available_indices()
