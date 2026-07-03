"""AllReduce 延迟模型：3D-torus 分维 ring AllReduce vs 单一大 ring。

关键洞察（也是 Google 选 torus 而非 fat-tree+单一集合通信的根因）：

把一次 AllReduce 沿 torus 的每个维度拆成一串 **短 ring AllReduce**（分层
reduce-scatter / allgather）。其 **延迟项 = 2 · Σ(d_i − 1) · α**，在大规模时
远低于把所有 N 个芯片串成单个大 ring 的 **2 · (N − 1) · α**——因为 Σ(d_i) 按
边长线性增长，而 N = Π(d_i) 按体积指数增长。带宽项两者渐近相同（≈ 2·m/β）。

例：16×16×16 = 4096 芯片
  - 单一大 ring：延迟项 = 2·4095·α = 8190α
  - torus 分维：延迟项 = 2·(15+15+15)·α = 90α   ← 约 90 倍差距
"""
from typing import Sequence


def ring_allreduce_time(ring_len: int, msg_bytes: int, bw: float, lat: float) -> float:
    """ring_len 个节点上对 msg_bytes 做 ring AllReduce 的时间。

    ring AllReduce = reduce-scatter（ring_len−1 步）+ allgather（ring_len−1 步），
    每步在链路上发送 msg_bytes / ring_len 字节。
    """
    if ring_len <= 1:
        return 0.0
    step_bytes = msg_bytes / ring_len
    return 2.0 * (ring_len - 1) * (lat + step_bytes / bw)


def torus_allreduce_time(
    dims: Sequence[int], msg_bytes: int, bw: float, lat: float
) -> float:
    """3D-torus 上的分层 ring AllReduce。

    依次沿每个维度做 reduce-scatter / allgather：进入第 i 维时，每个芯片持有
    msg / (d_0 · ... · d_{i-1}) 字节；该维环上每步发送 (持有量 / d_i) 字节。
    """
    t = 0.0
    shard = 1
    for d in dims:
        step_bytes = msg_bytes / (shard * d)
        t += 2.0 * (d - 1) * (lat + step_bytes / bw)
        shard *= d
    return t


def single_ring_time(n_nodes: int, msg_bytes: int, bw: float, lat: float) -> float:
    """对比基线：把所有 N 个芯片串成单个大 ring（fat-tree 上常见的做法）。"""
    return ring_allreduce_time(n_nodes, msg_bytes, bw, lat)


def latency_term(dims: Sequence[int]) -> float:
    """torus 分维 AllReduce 的延迟项系数（不含 α 乘子）：2·Σ(d_i − 1)。"""
    return 2.0 * sum(d - 1 for d in dims)
