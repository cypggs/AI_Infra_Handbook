import numpy as np

from ai_compiler_mini.triton_like import TilingConfig
from ai_compiler_mini.tune import autotune, best_config, config_space, heuristic_cost, traffic_for


def test_config_space_non_empty():
    space = config_space(128, 128, 128)
    assert len(space) > 0
    assert all(isinstance(c, TilingConfig) for c in space)


def test_config_space_respects_problem_size():
    space = config_space(16, 16, 16)
    assert all(c.BLOCK_M <= 32 and c.BLOCK_N <= 32 and c.BLOCK_K <= 32 for c in space)


def test_heuristic_cost_deterministic():
    cfg = TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=32, num_warps=4, num_stages=3)
    a = heuristic_cost(256, 256, 256, cfg)
    b = heuristic_cost(256, 256, 256, cfg)
    assert a.score == b.score
    assert a.detail == b.detail


def test_bigger_tile_less_repeated_traffic():
    small = heuristic_cost(256, 256, 256, TilingConfig(BLOCK_M=16, BLOCK_N=16, BLOCK_K=32))
    big = heuristic_cost(256, 256, 256, TilingConfig(BLOCK_M=128, BLOCK_N=128, BLOCK_K=32))
    assert big.detail["mem_ms"] < small.detail["mem_ms"]


def test_padding_waste_penalized():
    exact = heuristic_cost(128, 128, 128, TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=32))
    padded = heuristic_cost(130, 130, 128, TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=32))
    assert padded.detail["padding_waste"] > 0
    assert padded.detail["waste_ms"] > 0
    # 同样的 tile，不整除时浪费惩罚必须存在
    assert padded.score > exact.score - exact.detail["waste_ms"]


def test_autotune_top_k_sorted():
    top = autotune(128, 128, 128, top_k=5)
    assert len(top) == 5
    scores = [t.score for t in top]
    assert scores == sorted(scores)


def test_autotune_deterministic_same_best():
    c1 = best_config(256, 256, 256)
    c2 = best_config(256, 256, 256)
    assert c1 == c2


def test_best_prefers_less_traffic_for_large_gemm():
    cfg = best_config(512, 512, 512)
    # 大 GEMM 上最优解应当用较大的 tile 降低重复读
    assert cfg.BLOCK_M >= 32 and cfg.BLOCK_N >= 32


def test_traffic_for_matches_simulation():
    a = np.zeros((64, 64))
    b = np.zeros((64, 64))
    cfg = TilingConfig(BLOCK_M=32, BLOCK_N=32, BLOCK_K=32)
    # 4 个 program，每个读 (BM*K + K*BN) 元素、写 BM*BN 元素，float64 = 8B
    per_program = (32 * 64 + 64 * 32 + 32 * 32) * 8
    assert traffic_for(a, b, cfg) == 4 * per_program


def test_warps_stages_affect_score():
    base = heuristic_cost(256, 256, 256, TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=32, num_warps=4, num_stages=3))
    low_warps = heuristic_cost(256, 256, 256, TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=32, num_warps=2, num_stages=3))
    low_stages = heuristic_cost(256, 256, 256, TilingConfig(BLOCK_M=64, BLOCK_N=64, BLOCK_K=32, num_warps=4, num_stages=1))
    assert low_warps.score != base.score
    assert low_stages.score != base.score
