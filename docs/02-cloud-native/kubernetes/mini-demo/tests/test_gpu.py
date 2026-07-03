"""test_gpu.py — Device Plugin + GPU 调度测试。

覆盖：
  - GpuDevicePlugin.register 把 nvidia.com/gpu 并入容量并打 label
  - allocate 分配互不相同的设备索引；不足时抛错
  - release 释放；free 计数正确
  - env_for 注入 NVIDIA_VISIBLE_DEVICES
  - 端到端：3 个 GPU Pod 在 2 个 GPU 节点（各 2 卡）上各拿到独立设备
"""

import pytest

from k8s_mini.device_plugin import GpuDevicePlugin
from k8s_mini.model import Container, Node, Pod, Resources


def test_register_adds_capacity_and_labels():
    node = Node(name="g1", capacity=Resources(8000, 16000, 0))
    assert node.capacity.gpu == 0
    GpuDevicePlugin("g1", 4).register(node)
    assert node.capacity.gpu == 4
    assert node.labels.get("accelerator") == "nvidia"
    assert node.labels.get("nvidia.com/gpu.present") == "true"


def test_allocate_returns_distinct_indices():
    plug = GpuDevicePlugin("g1", 2)
    first = plug.allocate(1)
    second = plug.allocate(1)
    assert first != second
    assert set(first) | set(second) <= {0, 1}


def test_allocate_multi_gpu():
    plug = GpuDevicePlugin("g1", 8)
    got = plug.allocate(3)
    assert len(got) == 3 and len(set(got)) == 3
    assert plug.free == 5


def test_allocate_raises_when_insufficient():
    plug = GpuDevicePlugin("g1", 1)
    plug.allocate(1)
    with pytest.raises(RuntimeError):
        plug.allocate(1)


def test_release_frees_device():
    plug = GpuDevicePlugin("g1", 2)
    got = plug.allocate(2)
    assert plug.free == 0
    plug.release(got)
    assert plug.free == 2


def test_env_for_injects_visible_devices():
    plug = GpuDevicePlugin("g1", 4)
    env = plug.env_for([0, 2])
    assert env == {"NVIDIA_VISIBLE_DEVICES": "0,2"}


def test_env_for_empty_when_no_device():
    plug = GpuDevicePlugin("g1", 4)
    assert plug.env_for([]) == {}


# ----------------------------- 端到端（MiniCluster） -----------------------------

def test_three_gpu_pods_get_distinct_devices():
    from k8s_mini.demo import MiniCluster

    c = MiniCluster()
    c.add_node("gpu-node-1", cpu=8000, memory=16000, gpu=2)
    c.add_node("gpu-node-2", cpu=8000, memory=16000, gpu=2)

    def gpu_pod(name):
        return Pod(
            name=name,
            containers=[Container(name="vllm", image="vllm/vllm",
                                  requests=Resources(cpu=2000, memory=4096, gpu=1))],
            labels={"app": "vllm"},
        )

    for i in range(3):
        c.api.create_pod(gpu_pod(f"vllm-{i}"))
    c.run(ticks=3)

    placed = [p for p in c.api.list_pods() if p.name.startswith("vllm-")]
    # 3 个全部 Running 且各拿到恰好 1 张 GPU
    assert len(placed) == 3
    assert all(p.gpu_devices for p in placed)
    assert all(len(p.gpu_devices) == 1 for p in placed)
    # 全集群 GPU 使用 = 3
    total_free = sum(plug.free for plug in c.gpu_plugins.values())
    total_capacity = sum(plug.gpu_count for plug in c.gpu_plugins.values())
    assert total_capacity - total_free == 3


def test_gpu_request_exceeding_capacity_stays_unscheduled():
    from k8s_mini.demo import MiniCluster

    c = MiniCluster()
    c.add_node("gpu-node-1", cpu=8000, memory=16000, gpu=1)  # 仅 1 张卡
    big = Pod(
        name="big",
        containers=[Container(name="vllm", requests=Resources(cpu=1000, memory=512, gpu=2))],
    )
    c.api.create_pod(big)
    c.run(ticks=2)
    assert big.node_name == ""
    assert not big.scheduled
