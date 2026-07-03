"""3D-torus 拓扑：节点、链路与（OCS 可重配的）健康状态。

TPU v4 的核心网络选择是 **三维环面（3D-torus）**：每个芯片通过 6 条直连链路
（±x / ±y / ±z）与 6 个邻居相连，整体构成一个可环绕的立方网格。这与 NVIDIA
（fat-tree + NVLink）和 Meta（fat-tree）的拓扑截然不同——torus 的几何性让
集合通信可以被分解成沿三个维度的短 ring，从而把延迟项压到极低（见 collective.py）。
"""
from typing import Dict, List, Tuple


class Torus3D:
    """kx × ky × kz 的三维环面。

    坐标使用带环绕取模（torus：x 的邻居是 (x±1) % kx），因此边界节点与对侧节点相连，
    整个网格没有"边"。每个节点最多有 6 个邻居。
    """

    def __init__(self, dims: Tuple[int, int, int]):
        self.dims: Tuple[int, int, int] = (int(dims[0]), int(dims[1]), int(dims[2]))
        self._failed: Dict[int, bool] = {}

    @property
    def size(self) -> int:
        n = 1
        for d in self.dims:
            n *= d
        return n

    def to_index(self, x: int, y: int, z: int) -> int:
        """把 (x, y, z) 三维坐标映射到一维节点下标（行优先）。"""
        kx, ky, kz = self.dims
        return ((x % kx) * ky + (y % ky)) * kz + (z % kz)

    def to_xyz(self, index: int) -> Tuple[int, int, int]:
        """一维下标反解为 (x, y, z)。"""
        kx, ky, kz = self.dims
        z = index % kz
        rem = index // kz
        y = rem % ky
        x = rem // ky
        return (x, y, z)

    def neighbors(self, x: int, y: int, z: int) -> List[Tuple[int, int, int]]:
        """返回一个节点的 6 个 torus 邻居坐标（带环绕）。"""
        kx, ky, kz = self.dims
        out: List[Tuple[int, int, int]] = []
        for dx, dy, dz in (
            (1, 0, 0), (-1, 0, 0),
            (0, 1, 0), (0, -1, 0),
            (0, 0, 1), (0, 0, -1),
        ):
            out.append(((x + dx) % kx, (y + dy) % ky, (z + dz) % kz))
        return out

    def fail(self, node_index: int) -> None:
        """标记某芯片故障。"""
        self._failed[node_index] = True

    def heal(self, node_index: int) -> None:
        """修复某芯片（OCS 重配或后台维修后）。"""
        self._failed.pop(node_index, None)

    def is_failed(self, node_index: int) -> bool:
        return self._failed.get(node_index, False)

    def healthy_count(self) -> int:
        return self.size - len(self._failed)
