"""ring/tree all-reduce 步数与数据量模型（不同拓扑/fabric 下）。

闭式公式（通信理论标准模型，α-β 模型）：
- ring all-reduce：steps = 2(n-1)，每 rank 发送 2*(n-1)/n * M
  t_ring = 2(n-1)*α + 2(n-1)/n * M * β
- tree（递归倍增）all-reduce：steps = 2*ceil(log2 n)，但每 rank 发送
  ceil(log2 n)/2 * M（每步发半个消息，共 log2 n 步）——用更多字节换更少步数
  t_tree = 2*ceil(log2 n)*α + ceil(log2 n)/2 * M * β
- all-to-all：每 rank 发送 (n-1)/n * M，一轮完成
  t_a2a = α + (n-1)/n * M * β

教学要点：ring 与 tree 是"字节数换步数"的取舍——大消息（带宽受限）时
ring 的总字节 2(n-1)/n*M 优于 tree 的 log2(n)/2*M（n 较大时）；
小消息（时延受限）时 tree 的 2*log2(n) 步远优于 ring 的 2(n-1) 步。
"""

from __future__ import annotations

import math


# 示意 fabric 常量：(带宽 bps, 单步时延 s)。时延为量级示意值，非厂商 SLA。
FABRICS = {
    "NVLink5 (GB200)": (1.8e12, 0.3e-6),
    "NVLink4 (H100)": (900e9, 0.5e-6),
    "PCIe5 x16": (504e9, 1.0e-6),
    "InfiniBand NDR 400G": (400e9, 2.0e-6),
    "RoCE/以太网 400G": (400e9, 3.0e-6),
    "以太网 100G TCP": (100e9, 15.0e-6),
}


def ring_allreduce(n: int, message_bytes: float, bw_bps: float,
                   latency_s: float) -> dict:
    """ring all-reduce 的步数、每 rank 字节数、α-β 时延模型。"""
    if n < 2:
        raise ValueError("n >= 2")
    steps = 2 * (n - 1)
    bytes_per_rank = 2.0 * (n - 1) / n * message_bytes
    time_s = steps * latency_s + bytes_per_rank * 8 / bw_bps
    return {
        "algorithm": "ring",
        "steps": steps,
        "bytes_per_rank": bytes_per_rank,
        "time_s": time_s,
        "latency_part_s": steps * latency_s,
        "bandwidth_part_s": bytes_per_rank * 8 / bw_bps,
    }


def tree_allreduce(n: int, message_bytes: float, bw_bps: float,
                   latency_s: float) -> dict:
    """tree（递归倍增）all-reduce：步数 2*ceil(log2 n)，每 rank 发送 ceil(log2 n)/2 * M。"""
    if n < 2:
        raise ValueError("n >= 2")
    steps = 2 * math.ceil(math.log2(n))
    logn = math.ceil(math.log2(n))
    bytes_per_rank = logn / 2 * message_bytes
    time_s = steps * latency_s + bytes_per_rank * 8 / bw_bps
    return {
        "algorithm": "tree",
        "steps": steps,
        "bytes_per_rank": bytes_per_rank,
        "time_s": time_s,
        "latency_part_s": steps * latency_s,
        "bandwidth_part_s": bytes_per_rank * 8 / bw_bps,
    }


def alltoall(n: int, message_bytes: float, bw_bps: float,
             latency_s: float) -> dict:
    """all-to-all 一轮完成的通信模型（每 rank 同时向其余 n-1 个发送）。"""
    if n < 2:
        raise ValueError("n >= 2")
    bytes_per_rank = (n - 1) / n * message_bytes
    time_s = latency_s + bytes_per_rank * 8 / bw_bps
    return {
        "algorithm": "all-to-all",
        "steps": 1,
        "bytes_per_rank": bytes_per_rank,
        "time_s": time_s,
        "latency_part_s": latency_s,
        "bandwidth_part_s": bytes_per_rank * 8 / bw_bps,
    }


def compare_allreduce(n: int, message_bytes: float,
                      fabric_name: str = "InfiniBand NDR 400G") -> dict:
    """同一 fabric 上 ring vs tree 对比，并给出谁更快的判断依据。"""
    bw, lat = FABRICS[fabric_name]
    ring = ring_allreduce(n, message_bytes, bw, lat)
    tree = tree_allreduce(n, message_bytes, bw, lat)
    winner = "ring" if ring["time_s"] <= tree["time_s"] else "tree"
    reason = (
        "时延主导（小消息），tree 步数更少"
        if winner == "tree"
        else "带宽主导（大消息），ring 流水线更充分"
    )
    return {"ring": ring, "tree": tree, "winner": winner, "reason": reason}


def compare_fabrics(n: int, message_bytes: float,
                    algorithm: str = "ring") -> list:
    """同一算法在不同 fabric 上的耗时排序（展示 scale-up vs scale-out 的鸿沟）。"""
    fn = ring_allreduce if algorithm == "ring" else tree_allreduce
    rows = []
    for name, (bw, lat) in FABRICS.items():
        r = fn(n, message_bytes, bw, lat)
        rows.append({"fabric": name, "bw_bps": bw, "latency_s": lat,
                     "time_s": r["time_s"], "steps": r["steps"]})
    rows.sort(key=lambda r: r["time_s"])
    return rows


def bandwidth_delay_product(bw_bps: float, latency_s: float) -> float:
    """带宽时延积 BDP（字节）：一条流水线在途最多能"装"多少数据。"""
    if bw_bps <= 0 or latency_s < 0:
        raise ValueError("invalid args")
    return bw_bps * latency_s / 8


def step_speedup_from_faster_network(compute_time_s: float,
                                     comm_time_old_s: float,
                                     comm_time_new_s: float) -> dict:
    """通信提速对整个训练 step 的加速比（Amdahl 定律）。

    step_time = compute + comm；网络把 comm 从 old 降到 new。
    """
    if compute_time_s < 0 or comm_time_old_s <= 0 or comm_time_new_s < 0:
        raise ValueError("invalid times")
    old_step = compute_time_s + comm_time_old_s
    new_step = compute_time_s + comm_time_new_s
    return {
        "old_step_s": old_step,
        "new_step_s": new_step,
        "comm_fraction_before": comm_time_old_s / old_step,
        "speedup": old_step / new_step,
    }
