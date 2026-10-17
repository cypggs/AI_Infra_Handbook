"""朴素 auto-tuner（自动调优器）与启发式 cost model。

真实编译器（Triton autotune、TVM AutoTVM/Ansor、Inductor max-autotune）对同一
kernel 生成多种候选配置（tile 大小、warps、流水线级数），逐个打分或实测，选最优。

完整流程是「配置生成 -> 编译 -> 跑分（benchmark 或 cost model）-> 选最优」。
本模块实现确定性的启发式 cost model（不依赖 wall-clock，保证测试可复现）：

score = w_mem * 访存开销 + w_comp * 计算开销 + 启动开销 + 浪费惩罚

- 访存开销：用模拟器统计的 HBM 流量近似（tiling 越碎，A/B 被重复读得越多）
- 计算开销：FLOPs 恒定（2*M*N*K），但小 tile 导致 program 数过多，
  启动开销随 program 数线性增长
- 浪费惩罚：BLOCK 不能整除问题尺寸时，边缘 tile 有空转（padding waste）
- num_warps/stages：真实 GPU 上影响占用率与流水线；这里用温和启发式项模拟
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .triton_like import TilingConfig, grid_for, run_tiled_matmul


# 机器常数（模拟一张 H100 量级的卡，只用于把单位折算成可比较的分数）
PEAK_TFLOPS = 989.0  # ~BF16 dense 峰值
HBM_BW_GBS = 3350.0  # ~HBM3e
DTYPE_BYTES = 2.0  # bf16；模拟器内部用 float64，打分按 2 字节估算


@dataclass
class ScoredConfig:
    config: TilingConfig
    score: float  # 越低越好（预估毫秒数）
    detail: Dict[str, float]


def config_space(m: int, n: int, k: int) -> List[TilingConfig]:
    """生成候选配置空间（教学版剪枝：只保留不超过问题规模两倍的 tile）。"""
    block_choices = [16, 32, 64, 128]
    bm_opts = [b for b in block_choices if b <= max(16, 2 * m)]
    bn_opts = [b for b in block_choices if b <= max(16, 2 * n)]
    bk_opts = [b for b in block_choices if b <= max(16, 2 * k)]
    space: List[TilingConfig] = []
    for bm, bn, bk, w, s in itertools.product(bm_opts, bn_opts, bk_opts, [2, 4, 8], [2, 3, 4]):
        space.append(TilingConfig(BLOCK_M=bm, BLOCK_N=bn, BLOCK_K=bk, num_warps=w, num_stages=s))
    return space


def _padding_waste(m: int, n: int, cfg: TilingConfig) -> float:
    """边缘 tile 的空转比例（0 = 无浪费，越接近 1 浪费越严重）。"""
    gm, gn = grid_for(m, n, cfg)
    used_m = m / (gm * cfg.BLOCK_M)
    used_n = n / (gn * cfg.BLOCK_N)
    return 1.0 - used_m * used_n


def heuristic_cost(m: int, n: int, k: int, cfg: TilingConfig) -> ScoredConfig:
    """启发式打分：返回预估耗时（ms）与分解明细。纯函数，确定性。"""
    gm, gn = grid_for(m, n, cfg)
    # A 的每个 BM x K 条带被 gn 个 program 各读一次；B 的每个 K x BN 条带被 gm 次
    bytes_a = gm * cfg.BLOCK_M * k * DTYPE_BYTES * gn
    bytes_b = gn * cfg.BLOCK_N * k * DTYPE_BYTES * gm
    # 截断到真实尺寸（最后一个 tile 可能不满）
    bytes_a = min(bytes_a, m * k * DTYPE_BYTES * gn)
    bytes_b = min(bytes_b, n * k * DTYPE_BYTES * gm)
    bytes_c = m * n * DTYPE_BYTES
    traffic_gb = (bytes_a + bytes_b + bytes_c) / 1e9
    mem_ms = traffic_gb / (HBM_BW_GBS / 1000.0)

    flops = 2.0 * m * n * k
    comp_ms = flops / (PEAK_TFLOPS * 1e9) * 1000.0 * _compute_efficiency(cfg)

    launch_ms = (gm * gn) * 1e-6  # 每个 program ~1us 启动/收尾（教学常数）

    waste = _padding_waste(m, n, cfg)
    waste_ms = waste * (mem_ms + comp_ms) * 0.5

    score = mem_ms + comp_ms + launch_ms + waste_ms
    return ScoredConfig(
        config=cfg,
        score=score,
        detail={
            "mem_ms": mem_ms,
            "comp_ms": comp_ms,
            "launch_ms": launch_ms,
            "waste_ms": waste_ms,
            "padding_waste": waste,
            "programs": float(gm * gn),
        },
    )


def _compute_efficiency(cfg: TilingConfig) -> float:
    """小 tile / 过少 warp / 过浅流水线时有效算力下降的模拟（>=1 的惩罚系数）。

    更多 warp 与更深的流水线能更好地隐藏访存延迟，真实 GPU 上对应更高的
    Tensor Core 利用率；这里是温和的确定性近似。
    """
    penalty = 1.0
    if cfg.BLOCK_M < 32 or cfg.BLOCK_N < 32:
        penalty += 0.4
    if cfg.num_warps < 4:
        penalty += 0.15
    elif cfg.num_warps > 4:
        penalty += 0.05  # warp 过多带来同步开销
    if cfg.num_stages < 2:
        penalty += 0.3
    elif cfg.num_stages >= 3:
        penalty -= 0.05  # 深流水线隐藏延迟
    return max(penalty, 0.5)


def autotune(
    m: int,
    n: int,
    k: int,
    configs: Sequence[TilingConfig] | None = None,
    top_k: int = 3,
) -> List[ScoredConfig]:
    """对配置空间打分并返回 top_k（按 score 升序）。确定性。"""
    space = list(configs) if configs is not None else config_space(m, n, k)
    scored = [heuristic_cost(m, n, k, c) for c in space]
    scored.sort(key=lambda s: (s.score, s.config.BLOCK_M, s.config.BLOCK_N))
    return scored[:top_k]


def best_config(m: int, n: int, k: int, configs: Sequence[TilingConfig] | None = None) -> TilingConfig:
    return autotune(m, n, k, configs, top_k=1)[0].config


def traffic_for(a: np.ndarray, b: np.ndarray, cfg: TilingConfig) -> int:
    """用模拟器实测一次分块 GEMM 的全局内存流量（字节），用于验证 cost model。"""
    _, stats = run_tiled_matmul(a, b, cfg)
    return stats.total_traffic_bytes


def tiling_intuition_table(m: int, n: int, k: int) -> List[Tuple[str, int]]:
    """展示 tiling 对流量的影响：BLOCK 越小，A/B 被重复读的次数越多。"""
    rows: List[Tuple[str, int]] = []
    for bm in (16, 32, 64, 128):
        for bn in (16, 32, 64, 128):
            cfg = TilingConfig(BLOCK_M=bm, BLOCK_N=bn, BLOCK_K=32)
            a = np.zeros((m, k))
            b = np.zeros((k, n))
            rows.append((f"BM={bm:>3} BN={bn:>3}", traffic_for(a, b, cfg)))
    return rows
