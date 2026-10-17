import numpy as np
import pytest

from ai_compiler_mini.triton_like import (
    FusedRowwiseKernel,
    KernelStats,
    TilingConfig,
    grid_for,
    launch,
    run_tiled_matmul,
    unfused_rowwise_reference,
)


def test_tiling_config_validation():
    with pytest.raises(ValueError):
        TilingConfig(BLOCK_M=0)
    with pytest.raises(ValueError):
        TilingConfig(BLOCK_M=32, BLOCK_N=32, BLOCK_K=32, num_warps=0)
    with pytest.raises(ValueError):
        TilingConfig(BLOCK_M=32, BLOCK_N=32, BLOCK_K=32, num_stages=-1)


def test_tiled_matmul_matches_numpy_square():
    rng = np.random.default_rng(0)
    a = rng.standard_normal((64, 64))
    b = rng.standard_normal((64, 64))
    cfg = TilingConfig(BLOCK_M=32, BLOCK_N=32, BLOCK_K=32)
    c, _ = run_tiled_matmul(a, b, cfg)
    assert np.allclose(c, a @ b)


def test_tiled_matmul_ragged_edges():
    """M/K/N 均不整除 BLOCK 时仍正确。"""
    rng = np.random.default_rng(1)
    a = rng.standard_normal((50, 37))
    b = rng.standard_normal((37, 23))
    cfg = TilingConfig(BLOCK_M=16, BLOCK_N=16, BLOCK_K=16)
    c, stats = run_tiled_matmul(a, b, cfg)
    assert np.allclose(c, a @ b)
    gm, gn = grid_for(50, 23, cfg)
    assert stats.programs_launched == gm * gn


def test_stats_count_loads_and_stores():
    rng = np.random.default_rng(3)
    a = rng.standard_normal((32, 32))
    b = rng.standard_normal((32, 32))
    cfg = TilingConfig(BLOCK_M=32, BLOCK_N=32, BLOCK_K=32)
    _, stats = run_tiled_matmul(a, b, cfg)
    # 单 program：读 A(32x32) + B(32x32)，写 C(32x32)，float64 = 8B
    assert stats.global_loads_bytes == 2 * 32 * 32 * 8
    assert stats.global_stores_bytes == 32 * 32 * 8
    assert stats.total_traffic_bytes == 3 * 32 * 32 * 8


def test_smaller_blocks_repeat_traffic():
    """BLOCK 减半 -> A/B 被更多 program 重复读取 -> 流量上升。"""
    rng = np.random.default_rng(4)
    a = rng.standard_normal((64, 64))
    b = rng.standard_normal((64, 64))
    _, big = run_tiled_matmul(a, b, TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=64))
    _, small = run_tiled_matmul(a, b, TilingConfig(BLOCK_M=16, BLOCK_N=16, BLOCK_K=64))
    assert small.total_traffic_bytes > big.total_traffic_bytes


def test_launch_iterates_all_pids():
    seen = []
    stats = KernelStats()
    launch((2, 3), lambda p0, p1: seen.append((p0, p1)), stats)
    assert sorted(seen) == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
    assert stats.programs_launched == 6


def test_fused_rowwise_sum_correct():
    x = np.array([[1.0, -2.0, 3.0], [4.0, 5.0, -6.0]])
    stats = KernelStats()
    kernel = FusedRowwiseKernel(preprocess=lambda v: np.maximum(v, 0.0), reduce="sum")
    out = kernel.run(x, stats)
    assert np.allclose(out, np.array([4.0, 9.0]))


def test_fused_saves_traffic_vs_unfused():
    rng = np.random.default_rng(5)
    x = rng.standard_normal((64, 48))
    fused_stats = KernelStats()
    FusedRowwiseKernel(preprocess=lambda v: np.maximum(v, 0.0), reduce="sum").run(x, fused_stats)
    _, unfused = unfused_rowwise_reference(x, lambda v: np.maximum(v, 0.0), "sum")
    assert fused_stats.total_traffic_bytes < unfused.total_traffic_bytes
    # 未融合多一次中间结果的写 + 读
    mid = x.size * 8
    assert unfused.total_traffic_bytes - fused_stats.total_traffic_bytes == 2 * mid


def test_fused_and_unfused_results_identical():
    rng = np.random.default_rng(6)
    x = rng.standard_normal((32, 24))
    stats = KernelStats()
    fused = FusedRowwiseKernel(preprocess=lambda v: np.exp(-np.abs(v)), reduce="sum").run(x, stats)
    unfused, _ = unfused_rowwise_reference(x, lambda v: np.exp(-np.abs(v)), "sum")
    assert np.allclose(fused, unfused)
