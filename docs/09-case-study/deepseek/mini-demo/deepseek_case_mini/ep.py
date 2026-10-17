"""ep.py：专家并行（Expert Parallelism, EP）all-to-all 通信量模拟。

复现 DeepSeek-V3 技术报告 §3.2.2 的核心账：

- MoE 前向中每个 token 经 router 选择 top-k 个专家；在 EP 组内，
  dispatch（发送）与 combine（回收求和）各发生一次 all-to-all；
- 通信量 = token 数 × topk × hidden × 字节数 × 2（dispatch+combine）；
- 组内（同节点 8 卡，NVLink）与组间（跨节点，IB/RoCE）带宽差一个量级，
  DeepSeek 用 **节点受限路由（node-limited routing）** 把每个 token 的
  k 个专家限制在 M 个节点内，把大部分通信压在 NVLink 上；
- 通信时间由 **最慢的那张卡** 决定（all-to-all 同步性）⇒ 负载不均是
  EP 的头号敌人，这正是 EPLB（Expert-Parallel Load Balancer）存在的理由。

模型为均匀假设的简化模型（详见各函数 docstring），用于讲清量级与趋势。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# V3 训练配置常量（技术报告 §3.2：16 路 PP、64 路 EP 跨 8 节点、ZeRO-1 DP）
V3_HIDDEN = 7168
V3_TOPK = 8
V3_ROUTED_EXPERTS = 256
V3_SHARED_EXPERTS = 1
V3_NODE_SIZE = 8  # 每节点 8 张 H800
V3_EP_SIZE = 64  # EP 组跨 8 个节点
V3_NODES_LIMITED = 4  # node-limited routing: 每 token 最多落在 4 个节点


@dataclass(frozen=True)
class EpConfig:
    """一次 all-to-all 的 EP 配置。"""

    ep_size: int = V3_EP_SIZE  # EP 组 GPU 数
    node_size: int = V3_NODE_SIZE  # 每节点 GPU 数
    topk: int = V3_TOPK  # 每 token 路由的专家数
    hidden: int = V3_HIDDEN  # hidden size
    dtype_bytes: int = 2  # BF16 = 2 字节；FP8 dispatch = 1
    fp8_dispatch: bool = False  # DeepEP 支持 FP8 dispatch（输入量化后发送）
    nodes_limited: int | None = V3_NODES_LIMITED  # None 表示不限制

    @property
    def num_nodes(self) -> int:
        return self.ep_size // self.node_size


def token_payload_bytes(cfg: EpConfig) -> int:
    """每个 token 被复制 topk 份后的单份负载字节数。

    DeepEP 支持 FP8 dispatch（输入先量化到 FP8 再发送），开启后负载
    按 1 字节/元素计（缩放因子开销忽略，示意）。
    """
    bytes_per_elem = 1 if cfg.fp8_dispatch else cfg.dtype_bytes
    return cfg.hidden * bytes_per_elem


def dispatch_bytes_per_gpu(tokens_per_gpu: int, cfg: EpConfig) -> float:
    """单卡一次 dispatch 需要发出的总字节数（发给 EP 组内其它所有卡）。

    均匀假设：EP 组内每张卡收到等量 token 副本（负载均衡时成立）。
    """
    return float(tokens_per_gpu * cfg.topk * token_payload_bytes(cfg))


def combine_bytes_per_gpu(tokens_per_gpu: int, cfg: EpConfig) -> float:
    """combine 的通信量与 dispatch 对称（token 副本带着专家输出返回）。"""
    return dispatch_bytes_per_gpu(tokens_per_gpu, cfg)


def inter_node_fraction(cfg: EpConfig) -> float:
    """跨节点（走 IB）字节占比的均匀模型。

    不限制节点时（M = 全部节点），token 副本均匀落到 EP 组所有卡，
    其中 7/8 落到其它节点 ⇒ 跨节点占比 7/8（8 卡节点）。
    限制到 M 个节点时，跨节点节点数从 (N-1) 缩到 (M-1)，
    占比 = (M-1)/(N-1) × 7/8。
    """
    n = cfg.num_nodes
    if n == 1:
        return 0.0
    m = cfg.nodes_limited if cfg.nodes_limited is not None else n
    m = max(1, min(m, n))
    base = (cfg.node_size - 1) / cfg.node_size  # 不限节点时的跨节点占比
    return (m - 1) / (n - 1) * base if n > 1 else 0.0


def split_traffic(total_bytes: float, cfg: EpConfig) -> tuple[float, float]:
    """把总字节拆成 (NVLink 字节, IB 字节)。"""
    inter = inter_node_fraction(cfg)
    return total_bytes * (1.0 - inter), total_bytes * inter


def all_to_all_time(
    total_bytes: float,
    cfg: EpConfig,
    nvlink_bw: float = 400e9,  # H800 NVLink ~400 GB/s 每卡（A800/H800 被削减后的规格）
    ib_bw: float = 50e9,  # 400 Gb/s IB ≈ 50 GB/s 每卡
    imbalance: float = 1.0,
) -> float:
    """一次 dispatch 或 combine 的通信时间（秒）。

    NVLink 与 IB 两段并行流水，瓶颈为两段之和 × 负载不均因子
    （最慢卡决定整体进度；imbalance = 最大卡接收量 / 平均接收量）。
    """
    nv, ib = split_traffic(total_bytes, cfg)
    t = nv / nvlink_bw + ib / ib_bw
    return t * imbalance


def expert_loads(
    tokens_per_gpu: int, cfg: EpConfig, seed: int = 0
) -> list[float]:
    """模拟每张卡上各专家的接收 token 数（含共享专家不计路由）。

    均匀情形：每专家期望接收 = tokens×topk/ep_size。
    用 seeded Dirichlet 扰动模拟 router 的天然偏斜，返回每专家负载列表。
    """
    rng = np_random(seed)
    base = tokens_per_gpu * cfg.topk / cfg.ep_size
    # Gamma 扰动 ⇒ 期望 1.0，形状参数越小越不均
    shape = 4.0
    weights = rng.gamma(shape, 1.0 / shape, size=cfg.ep_size)
    weights /= weights.mean()
    return (weights * base).tolist()


def imbalance_factor(loads: list[float]) -> float:
    """最大卡接收量 / 平均接收量。"""
    avg = sum(loads) / len(loads)
    if avg == 0.0:
        return 1.0
    return max(loads) / avg


def routing_imbalance(tokens_per_gpu: int, cfg: EpConfig, seed: int = 0) -> float:
    """从模拟路由分布直接算出不均因子。"""
    return imbalance_factor(expert_loads(tokens_per_gpu, cfg, seed))


def np_random(seed: int):
    return np.random.default_rng(seed)


def ep_step_comm_time(
    tokens_per_gpu: int,
    cfg: EpConfig,
    seed: int = 0,
    nvlink_bw: float = 400e9,
    ib_bw: float = 50e9,
) -> dict:
    """一个 MoE 层前向+反向的 EP 通信时间账（dispatch×2 + combine×2）。

    前向：dispatch + combine；反向：梯度再走一轮（combine 的梯度 = dispatch，
    dispatch 的梯度 = combine），量级相同 ⇒ 反向 ≈ 前向。
    返回 dict 便于测试与打印。
    """
    imb = routing_imbalance(tokens_per_gpu, cfg, seed)
    dispatch_b = dispatch_bytes_per_gpu(tokens_per_gpu, cfg)
    fwd = all_to_all_time(dispatch_b, cfg, nvlink_bw, ib_bw, imb) * 2.0
    bwd = fwd  # 对称
    return {
        "dispatch_bytes": dispatch_b,
        "imbalance": imb,
        "forward_seconds": fwd,
        "backward_seconds": bwd,
        "total_seconds": fwd + bwd,
    }
