"""极度简化的 "Triton-like" tile kernel 模拟器。

Triton 的核心编程模型（见 openai/triton 官方教程）：

- kernel 以「一个 program 处理一个 tile」为单位思考，而不是以线程为单位
- 程序用 pid（program id）在 launch grid 中定位自己负责的 tile
- 每个 program 内部对 tile 做 load -> compute -> store，
  中间结果留在「片上」（真实 GPU 是寄存器 + shared memory，这里用 numpy 局部数组模拟）

本模块在 numpy 上复刻这套语义：

- launch(grid, program)       模拟 kernel launch，grid = (M_blocks, N_blocks)
- matmul_kernel(pids, tiles)  每个 program 计算 C[pid_m*BM:(pid_m+1)*BM, ...]
  的 tile，K 维在 program 内部按 BLOCK_K 循环（模拟 num_stages 流水线被
  折叠后的最终结果）
- FusedRowwiseKernel      模拟「elementwise + reduce」融合 kernel：
  一行数据只从「全局内存」读一次、写一次（真实 Triton 里这就是
  tl.max / tl.sum 配 elementwise 的融合 kernel）

同时统计每个 kernel 的「全局内存访问量」，供 cost model / auto-tuner 打分。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np


@dataclass
class KernelStats:
    """一次 kernel 模拟执行的统计。"""

    global_loads_bytes: int = 0
    global_stores_bytes: int = 0
    programs_launched: int = 0

    @property
    def total_traffic_bytes(self) -> int:
        return self.global_loads_bytes + self.global_stores_bytes


@dataclass
class TilingConfig:
    """GEMM tile 配置，字段命名对齐 Triton 的 matmul 教程。

    BLOCK_M / BLOCK_N / BLOCK_K 是 CTA 级 tile；num_warps / num_stages
    在真实 GPU 上影响占用率与流水线深度，CPU 模拟中只参与打分。
    """

    BLOCK_M: int = 32
    BLOCK_N: int = 32
    BLOCK_K: int = 32
    num_warps: int = 4
    num_stages: int = 3

    def __post_init__(self) -> None:
        for f in ("BLOCK_M", "BLOCK_N", "BLOCK_K"):
            if getattr(self, f) <= 0:
                raise ValueError(f"{f} 必须为正整数")
        if self.num_warps <= 0 or self.num_stages <= 0:
            raise ValueError("num_warps / num_stages 必须为正整数")


def grid_for(m: int, n: int, cfg: TilingConfig) -> Tuple[int, int]:
    """launch grid 大小 = 每个维度需要的 tile 数（向上取整）。"""
    return ((m + cfg.BLOCK_M - 1) // cfg.BLOCK_M, (n + cfg.BLOCK_N - 1) // cfg.BLOCK_N)


def launch(grid: Sequence[int], program: Callable[..., None], stats: KernelStats) -> None:
    """模拟 kernel launch：遍历 grid 中的每个 pid，调用 program(*pid)。

    grid 语义与 Triton 的 triton.cdiv 网格完全一致。
    """
    stats.programs_launched += int(np.prod(grid))
    if len(grid) == 1:
        for p in range(grid[0]):
            program(p)
    elif len(grid) == 2:
        for p0 in range(grid[0]):
            for p1 in range(grid[1]):
                program(p0, p1)
    else:
        raise ValueError("mini 模拟器最多支持二维 grid")


def matmul_kernel(
    pid_m: int,
    pid_n: int,
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
    cfg: TilingConfig,
    stats: KernelStats,
) -> None:
    """一个 program 的语义：C 的一个 BM x BN tile 的全部计算。

    对应 Triton 教程 matmul kernel 中 program_id 轴为 (M, N) 的版本：

        offs_am = pid_m * BLOCK_M + arange(BLOCK_M)
        acc = zeros((BM, BN))
        for k in range(0, K, BLOCK_K):
            a_tile = load(A[offs_am, k:k+BK])   # -> 统计为全局读
            b_tile = load(B[k:k+BK, offs_bn])   # -> 统计为全局读
            acc += dot(a_tile, b_tile)          # 片上累加，无全局访存
        store(C[offs_am, offs_bn], acc)         # -> 统计为全局写
    """
    m, k = a.shape
    _, n = b.shape
    row0, row1 = pid_m * cfg.BLOCK_M, min((pid_m + 1) * cfg.BLOCK_M, m)
    col0, col1 = pid_n * cfg.BLOCK_N, min((pid_n + 1) * cfg.BLOCK_N, n)
    bm, bn = row1 - row0, col1 - col0
    acc = np.zeros((bm, bn), dtype=np.float64)
    for k0 in range(0, k, cfg.BLOCK_K):
        k1 = min(k0 + cfg.BLOCK_K, k)
        a_tile = a[row0:row1, k0:k1]
        b_tile = b[k0:k1, col0:col1]
        stats.global_loads_bytes += (a_tile.size + b_tile.size) * 8  # float64
        acc += a_tile @ b_tile
    c[row0:row1, col0:col1] = acc
    stats.global_stores_bytes += acc.size * 8


def run_tiled_matmul(a: np.ndarray, b: np.ndarray, cfg: TilingConfig) -> Tuple[np.ndarray, KernelStats]:
    """完整模拟一次分块 GEMM：launch grid -> 逐 program 执行 -> 返回结果与统计。"""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[0]:
        raise ValueError(f"形状不匹配: {a.shape} x {b.shape}")
    m, n = a.shape[0], b.shape[1]
    c = np.zeros((m, n), dtype=np.float64)
    stats = KernelStats()
    g = grid_for(m, n, cfg)
    launch(g, lambda pm, pn: matmul_kernel(pm, pn, a, b, c, cfg, stats), stats)
    return c, stats


class FusedRowwiseKernel:
    """模拟「elementwise 链 + 行归约」的融合 kernel（Triton 风格）。

    真实场景：rowwise softmax = max(行) -> exp(x - max) -> sum(行) -> div。
    eager 执行需要 ~5 次 kernel launch 与 5 次全局内存往返；
    融合后每行只读一次、写一次。

    本模拟器用 stats 精确展示这种流量差异，并支持任意的
    elementwise 预处理函数（如 relu / sigmoid / 减法）。
    """

    def __init__(self, preprocess: Callable[[np.ndarray], np.ndarray], reduce: str = "sum") -> None:
        if reduce not in ("sum", "max"):
            raise ValueError("mini 模拟器支持 sum / max 两种行归约")
        self.preprocess = preprocess
        self.reduce = reduce

    def run(self, x: np.ndarray, stats: KernelStats) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if x.ndim != 2:
            raise ValueError("FusedRowwiseKernel 只支持二维输入（行 x 列）")
        stats.global_loads_bytes += x.size * 8
        out = np.empty(x.shape[0], dtype=np.float64)
        for row in range(x.shape[0]):  # 每行 = 一个 program（grid = M）
            stats.programs_launched += 1
            line = x[row]
            t = self.preprocess(line)  # 中间结果留在「片上」，不产生全局访存
            out[row] = t.sum() if self.reduce == "sum" else t.max()
        stats.global_stores_bytes += out.size * 8
        return out


def unfused_rowwise_reference(
    x: np.ndarray, preprocess: Callable[[np.ndarray], np.ndarray], reduce: str
) -> Tuple[np.ndarray, KernelStats]:
    """同一个计算的「未融合 eager 版本」：每个中间张量都读写全局内存。

    返回 (结果, 统计)，供与融合版本做流量对比。
    """
    x = np.asarray(x, dtype=np.float64)
    stats = KernelStats()
    stats.global_loads_bytes += x.size * 8  # load x
    t = preprocess(x)
    stats.global_stores_bytes += t.size * 8  # store 中间结果
    stats.global_loads_bytes += t.size * 8  # load 中间结果
    if reduce == "sum":
        out = t.sum(axis=1)
    else:
        out = t.max(axis=1)
    stats.global_stores_bytes += out.size * 8
    return out, stats
