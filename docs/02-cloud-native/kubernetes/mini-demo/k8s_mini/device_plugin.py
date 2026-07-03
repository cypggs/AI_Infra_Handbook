"""device_plugin.py — Device Plugin 的极简模拟（NVIDIA Device Plugin）。

真实机制：Device Plugin 向 kubelet 注册，上报扩展资源容量（如 nvidia.com/gpu=8），
kubelet 在调度时把该容量计入 Node.allocatable；syncPod 时调用 Allocate() 给容器分配
具体设备并注入 NVIDIA_VISIBLE_DEVICES 环境变量与 /dev/nvidia* 挂载。

本模拟：注册时把 gpu 容量并入 node.capacity；allocate 时返回被分配的设备索引。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_mini.model import Node


@dataclass
class GpuDevicePlugin:
    """NVIDIA Device Plugin 的教学版。"""

    node_name: str
    gpu_count: int  # 节点上的 GPU 张数
    # 已分配的 GPU 索引集合（GPU 默认整数独占，除非 MIG/MPS）
    allocated: set[int] = field(default_factory=set)

    def register(self, node: Node) -> None:
        """注册：把 nvidia.com/gpu 容量并入节点 capacity。

        真实 K8s：kubelet 通过 ListAndWatch gRPC 上报 node.status.allocatable["nvidia.com/gpu"]。
        """
        node.capacity.gpu += self.gpu_count
        # 同时给节点打 label，供 NodeAffinity/NodeSelector 使用
        node.labels.setdefault("accelerator", "nvidia")
        node.labels.setdefault("nvidia.com/gpu.present", "true")

    @property
    def free(self) -> int:
        return self.gpu_count - len(self.allocated)

    def allocate(self, count: int) -> list[int]:
        """分配 count 个 GPU，返回设备索引列表。"""
        if count > self.free:
            raise RuntimeError(
                f"insufficient gpu on {self.node_name}: want {count}, free {self.free}"
            )
        free_indices = [i for i in range(self.gpu_count) if i not in self.allocated]
        chosen = free_indices[:count]
        self.allocated.update(chosen)
        return chosen

    def release(self, indices: list[int]) -> None:
        for i in indices:
            self.allocated.discard(i)

    def env_for(self, indices: list[int]) -> dict[str, str]:
        """注入容器的环境变量（真实 NVIDIA runtime 据此限制可见 GPU）。"""
        if not indices:
            return {}
        return {"NVIDIA_VISIBLE_DEVICES": ",".join(str(i) for i in indices)}
