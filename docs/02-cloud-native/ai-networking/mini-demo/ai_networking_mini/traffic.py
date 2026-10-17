"""并行策略流量矩阵模拟：TP / DP / EP / PP 的大小、频率与热点因子。

对应真实世界（一个 transformer 训练 step 内的集合通信）：
- DP（数据并行 / ZeRO）：梯度 reduce-scatter + all-gather，每 step 一次，大象流
- TP（张量并行）：每层 2 次 all-reduce，每 microbatch 都发生，频率最高、时延最敏感
- EP（MoE 专家并行）：每层 dispatch + combine 两次 all-to-all，扇出大、易 incast
- PP（流水并行）：相邻 stage 点对点 send/recv 激活值，量小但延迟敏感

所有矩阵都是 numpy 数组（字节数），公式为通信理论的标准闭式表达。
"""

from __future__ import annotations

import numpy as np

GIB = 1024 ** 3


# ---------------------------------------------------------------------------
# 基本流量矩阵
# ---------------------------------------------------------------------------

def ring_edges(n: int) -> list:
    """n 个 rank 的 ring 拓扑有向边：i -> (i+1) % n。"""
    if n < 2:
        raise ValueError("ring needs n >= 2")
    return [(i, (i + 1) % n) for i in range(n)]


def matrix_from_edges(n: int, edges: list, bytes_per_edge: float) -> np.ndarray:
    """有向边列表 + 每边字节数 -> n×n 流量矩阵 M[src][dst]。"""
    m = np.zeros((n, n), dtype=np.float64)
    for src, dst in edges:
        m[src, dst] += bytes_per_edge
    return m


def uniform_alltoall_matrix(n: int, per_pair_bytes: float) -> np.ndarray:
    """均匀 all-to-all：每对 rank 互发 per_pair_bytes，对角线为 0。"""
    m = np.full((n, n), per_pair_bytes, dtype=np.float64)
    np.fill_diagonal(m, 0.0)
    return m


def skewed_alltoall_matrix(n: int, per_pair_bytes: float, hot_rank: int = 0,
                           skew: float = 2.0) -> np.ndarray:
    """带倾斜的 all-to-all：模拟 MoE 热门 expert 所在 rank 收到更多 token。

    hot_rank 的入向流量放大 (1 + skew) 倍。
    """
    m = uniform_alltoall_matrix(n, per_pair_bytes)
    m[:, hot_rank] *= (1.0 + skew)
    return m


def pp_pipeline_matrix(n_stages: int, activation_bytes: float,
                       n_microbatches: int) -> np.ndarray:
    """流水并行：相邻 stage 之间每个 microbatch 前向+反向各传一次激活。"""
    fwd = matrix_from_edges(n_stages, [(i, i + 1) for i in range(n_stages - 1)],
                            activation_bytes * n_microbatches)
    bwd = matrix_from_edges(n_stages, [(i + 1, i) for i in range(n_stages - 1)],
                            activation_bytes * n_microbatches)
    return fwd + bwd


# ---------------------------------------------------------------------------
# 矩阵统计：热点因子 / incast 因子
# ---------------------------------------------------------------------------

def matrix_stats(m: np.ndarray) -> dict:
    """流量矩阵统计。

    - hotspot_factor：最大行和 / 平均行和（发送侧不均衡度，1.0 为完全均匀）
    - incast_factor：最大列和 / 平均列和（接收侧扇入集中度）
    """
    row = m.sum(axis=1)
    col = m.sum(axis=0)
    return {
        "total_bytes": float(m.sum()),
        "per_rank_send_mean": float(row.mean()),
        "per_rank_send_max": float(row.max()),
        "per_rank_send_min": float(row.min()),
        "hotspot_factor": float(row.max() / row.mean()) if row.mean() else 0.0,
        "incast_factor": float(col.max() / col.mean()) if col.mean() else 0.0,
    }


# ---------------------------------------------------------------------------
# 闭式公式：每次通信的字节数
# ---------------------------------------------------------------------------

def allreduce_send_bytes(message_bytes: float, n: int) -> float:
    """ring all-reduce 每个 rank 的发送量：2*(n-1)/n * M。"""
    if n < 2:
        return 0.0
    return 2.0 * (n - 1) / n * message_bytes


def alltoall_send_bytes(message_bytes: float, n: int) -> float:
    """all-to-all 每个 rank 的发送量：(n-1)/n * M。"""
    if n < 2:
        return 0.0
    return (n - 1) / n * message_bytes


def dp_gradient_bytes(params_bytes: float, n_ranks: int,
                      overlap: bool = False) -> dict:
    """DP/ZeRO 每 step 的梯度同步流量。

    - 朴素 DDP：一次 all-reduce，量 = 2*(n-1)/n * P
    - ZeRO（reduce-scatter + all-gather）：总发送量与 all-reduce 相同（2*(n-1)/n * P），
      但每次通信的消息更短、启动更早（可与反向计算 overlap）
    """
    base = allreduce_send_bytes(params_bytes, n_ranks)
    return {
        "pattern": "allreduce" if not overlap else "reduce-scatter + all-gather",
        "bytes_per_rank": base,
        "times_per_step": 1,
        "overlap_backward": overlap,
    }


def tp_allreduce_bytes(tp_message_bytes: float, n_tp: int,
                       local_layers: int, n_microbatches: int) -> dict:
    """TP 每 step 流量：每层 2 次 all-reduce（column/row 各一），每 microbatch 发生。"""
    per_call = allreduce_send_bytes(tp_message_bytes, n_tp)
    return {
        "pattern": "allreduce (ring, 节点内 NVLink 域)",
        "bytes_per_rank": 2 * local_layers * n_microbatches * per_call,
        "times_per_step": 2 * local_layers * n_microbatches,
        "per_call_bytes": per_call,
    }


def ep_alltoall_bytes(token_bytes: float, topk: int, n_ep: int,
                      local_layers: int, n_microbatches: int) -> dict:
    """EP 每 step 流量：每层 dispatch + combine 两次 all-to-all。

    token_bytes = 每 microbatch 进入本 rank 的 token 激活总字节数。
    """
    per_call = alltoall_send_bytes(token_bytes * topk, n_ep)
    return {
        "pattern": "all-to-all (跨节点 scale-out 域)",
        "bytes_per_rank": 2 * local_layers * n_microbatches * per_call,
        "times_per_step": 2 * local_layers * n_microbatches,
        "per_call_bytes": per_call,
    }


def pp_p2p_bytes(activation_bytes: float, n_microbatches: int) -> dict:
    """PP 每 step 流量：每个 stage 边界、每个 microbatch 前向+反向各一次。"""
    return {
        "pattern": "p2p send/recv (相邻 stage)",
        "bytes_per_rank": 2 * n_microbatches * activation_bytes,
        "times_per_step": 2 * n_microbatches,
        "per_call_bytes": activation_bytes,
    }


def step_traffic_summary(config: dict) -> dict:
    """汇总一个训练 step 内各并行策略的流量（用于对比表）。

    config 字段：
      params_bytes, n_ranks, tp_message_bytes, n_tp, ep_token_bytes, topk, n_ep,
      local_layers, n_microbatches, activation_bytes
    """
    rows = {}
    rows["DP 梯度同步"] = dp_gradient_bytes(
        config["params_bytes"], config["n_ranks"], overlap=True)
    rows["TP 张量并行"] = tp_allreduce_bytes(
        config["tp_message_bytes"], config["n_tp"],
        config["local_layers"], config["n_microbatches"])
    if config.get("n_ep", 0) >= 2:
        rows["EP 专家并行"] = ep_alltoall_bytes(
            config["ep_token_bytes"], config["topk"], config["n_ep"],
            config["local_layers"], config["n_microbatches"])
    rows["PP 流水并行"] = pp_p2p_bytes(
        config["activation_bytes"], config["n_microbatches"])
    return rows


def dominant_traffic(rows: dict) -> str:
    """找出每 step 字节数最大的并行策略（通信瓶颈的 first order 判断）。"""
    return max(rows, key=lambda k: rows[k]["bytes_per_rank"])
