"""6 个端到端演示场景：量化工具链的核心权衡（纯 numpy、确定性）。

场景：
1. linear_quant      —— 同一权重在不同粒度/位宽下的量化误差对比
2. group_tradeoff    —— INT4 group size 权衡：误差 vs 等效位宽
3. smooth_quant      —— SmoothQuant 难度迁移的收益与 α 扫描
4. gptq_vs_rtn       —— 相关特征下 GPTQ 误差补偿 vs RTN
5. kv_long_context   —— KV 量化粒度选择对长上下文注意力的影响
6. fp4_fp8_formats   —— NVFP4/MXFP4/裸 FP4 与 FP8 E4M3/E5M2 的取舍
"""

from __future__ import annotations

import numpy as np

from . import gptq_like, kv_quant, smooth
from .quantize import (
    QuantConfig,
    block_float_quantize,
    effective_bits_per_weight,
    float_quantize,
    quantize_tensor,
    rel_l2_error,
)


# ---------------------------------------------------------------------------
# 场景 1：线性层量化误差对比
# ---------------------------------------------------------------------------


def scenario_linear_quant() -> dict:
    """同一权重在 per-tensor / per-channel / group-wise × INT8 / INT4 下的误差。"""
    rng = np.random.default_rng(0)
    W = rng.standard_normal((256, 512)) * 0.02
    results = {}
    for bits in (8, 4):
        for name, cfg in [
            ("per_tensor", QuantConfig(bits=bits, axis=1)),
            ("per_channel", QuantConfig(bits=bits, granularity="per_channel", axis=0)),
            ("group128", QuantConfig(bits=bits, granularity="group_wise", group_size=128, axis=1)),
            ("group32", QuantConfig(bits=bits, granularity="group_wise", group_size=32, axis=1)),
        ]:
            err = rel_l2_error(W, quantize_tensor(W, cfg).dequant())
            results[f"int{bits}_{name}"] = err
    print("=== 场景 1：线性层量化误差对比（W: 256×512, 对称量化, rel L2）===")
    for k, v in results.items():
        print(f"{k:>18}: {v:.6f}")
    return results


# ---------------------------------------------------------------------------
# 场景 2：group size 权衡
# ---------------------------------------------------------------------------


def scenario_group_tradeoff() -> dict:
    """INT4 group-wise：group size 越小误差越低，但等效位宽越高。"""
    rng = np.random.default_rng(0)
    W = rng.standard_normal((256, 512)) * 0.02
    results = {}
    for g in (32, 64, 128, 256):
        cfg = QuantConfig(bits=4, granularity="group_wise", group_size=g, axis=1)
        err = rel_l2_error(W, quantize_tensor(W, cfg).dequant())
        results[g] = (err, effective_bits_per_weight(cfg))
    # per-channel（每输出行一个 scale）相当于 g = 整行（512）
    cfg_pc = QuantConfig(bits=4, granularity="per_channel", axis=0)
    results[512] = (
        rel_l2_error(W, quantize_tensor(W, cfg_pc).dequant()),
        effective_bits_per_weight(cfg_pc),
    )
    print("=== 场景 2：INT4 group size 权衡（FP16 scale, 等效位宽=4+16/g）===")
    print(f"{'group':>6} {'rel_l2_err':>12} {'bits/weight':>12}")
    for g, (err, bits) in results.items():
        label = "per-channel" if g == 512 else str(g)
        print(f"{label:>6} {err:12.6f} {bits:12.4f}")
    return {str(k): {"err": v[0], "bits": v[1]} for k, v in results.items()}


# ---------------------------------------------------------------------------
# 场景 3：SmoothQuant 难度迁移
# ---------------------------------------------------------------------------


def scenario_smooth_quant() -> dict:
    """含离群通道的激活：平滑迁移前后 per-tensor INT8 输出误差 + α 扫描。"""
    rng = np.random.default_rng(3)
    W = rng.standard_normal((128, 256)) * 0.02
    X = smooth.make_outlier_activations(512, 256, n_outliers=4, outlier_scale=30.0, seed=1)
    sweep = smooth.alpha_sweep(W, X)
    print("=== 场景 3：SmoothQuant 难度迁移（W8A8 per-tensor INT8）===")
    print(f"{'alpha':>6} {'baseline':>12} {'smoothed':>12} {'reduction':>10}")
    out = {}
    for r in sweep:
        print(f"{r['alpha']:>6.2f} {r['baseline_err']:12.6f} {r['smoothed_err']:12.6f} {r['reduction_factor']:9.2f}x")
        out[f"alpha_{r['alpha']}"] = r["smoothed_err"]
    out["baseline"] = sweep[0]["baseline_err"]
    best = min(sweep, key=lambda r: r["smoothed_err"])
    out["best_alpha"] = best["alpha"]
    out["best_reduction"] = best["reduction_factor"]
    print(f"最优 alpha={best['alpha']}，误差降低 {best['reduction_factor']:.1f}x")
    return out


# ---------------------------------------------------------------------------
# 场景 4：GPTQ vs RTN
# ---------------------------------------------------------------------------


def scenario_gptq_vs_rtn() -> dict:
    """相关特征（低秩混合）下，INT4/INT8 的 GPTQ 与 RTN 误差对比。"""
    rng = np.random.default_rng(5)
    W = rng.standard_normal((64, 128)) * 0.05
    X = gptq_like.make_correlated_activations(256, 128, rank=16, seed=0)
    out = {}
    print("=== 场景 4：GPTQ（误差补偿）vs RTN（W: 64×128, 校准: 256×128 低秩相关）===")
    print(f"{'方案':>14} {'权重rel_l2':>12} {'输出rel_l2':>12}")
    for bits in (4, 8):
        g = 64 if bits == 4 else 128
        w_rtn = gptq_like.rtn_quantize(W, bits, g)
        w_gptq = gptq_like.gptq_quantize(W, X, bits, g)
        e_rtn_w = gptq_like.weight_rel_error(w_rtn, W)
        e_gptq_w = gptq_like.weight_rel_error(w_gptq, W)
        e_rtn_o = gptq_like.output_rel_error(X, w_rtn, W)
        e_gptq_o = gptq_like.output_rel_error(X, w_gptq, W)
        out[f"int{bits}_rtn_weight"] = e_rtn_w
        out[f"int{bits}_gptq_weight"] = e_gptq_w
        out[f"int{bits}_rtn_output"] = e_rtn_o
        out[f"int{bits}_gptq_output"] = e_gptq_o
        out[f"int{bits}_improve"] = e_rtn_o / e_gptq_o
        print(f"{'RTN  INT%d g=%d' % (bits, g):>14} {e_rtn_w:12.6f} {e_rtn_o:12.6f}")
        print(f"{'GPTQ INT%d g=%d' % (bits, g):>14} {e_gptq_w:12.6f} {e_gptq_o:12.6f}")
    print(f"INT4 输出误差改善: {out['int4_improve']:.2f}x，INT8: {out['int8_improve']:.2f}x")
    print("注：GPTQ 优化的是校准集输出误差而非权重范数，权重 rel_l2 可能更大")
    print("    （补偿扰动刻意落在校准数据的零空间里，对输出无影响）。")
    return out


# ---------------------------------------------------------------------------
# 场景 5：KV 量化与长上下文
# ---------------------------------------------------------------------------


def scenario_kv_long_context() -> dict:
    """不同 KV 量化配置下，注意力输出余弦相似度随上下文长度的变化。"""
    rng = np.random.default_rng(7)
    lengths = (128, 256, 384, 512)
    configs = [
        ("int8_channel", 8, "channel"),
        ("int4_channel", 4, "channel"),  # KIVI 推荐：K 按通道
        ("int4_token", 4, "token"),  # 反例：K 按 token
    ]
    out = {}
    print("=== 场景 5：KV 量化对长上下文注意力的影响（K 含通道离群 ×20, d=64）===")
    header = f"{'length':>7} " + " ".join(f"{n:>15}" for n, _, _ in configs)
    print(header + "   (平均余弦相似度)")
    for T in lengths:
        K, V = kv_quant.make_kv_cache(T, 64, seed=T)  # 每长度独立但确定性
        Q = rng.standard_normal((8, 64))
        row = [T]
        for name, bits, k_mode in configs:
            r = kv_quant.kv_quant_attention_error(Q, K, V, bits, group_size=32, k_mode=k_mode)
            out[f"{name}_{T}"] = r["cosine"]
            row.append(r["cosine"])
        print(f"{row[0]:>7} " + " ".join(f"{v:15.6f}" for v in row[1:]))
    print("读法：K 按通道分组（int4_channel）即使 512 token 上下文仍保持高相似度；")
    print("      K 按 token 分组（int4_token）被离群通道拖垮，且随长度劣化更快。")
    return out


# ---------------------------------------------------------------------------
# 场景 6：FP4 / FP8 浮点格式
# ---------------------------------------------------------------------------


def scenario_fp4_fp8_formats() -> dict:
    """NVFP4 vs MXFP4 vs 裸 E2M1（权重）；E4M3 vs E5M2（含离群激活）。"""
    rng = np.random.default_rng(11)
    W = rng.standard_normal((128, 512)) * 0.02
    out = {}
    print("=== 场景 6：FP4 格式对比（权重 W: 128×512, rel L2）===")
    for name, bs, sk in [("NVFP4(blk16,E4M3scale)", 16, "e4m3"), ("MXFP4(blk32,E8M0scale)", 32, "e8m0")]:
        x_hat, info = block_float_quantize(W, block_size=bs, scale_kind=sk)
        err = rel_l2_error(W, x_hat)
        out[name] = err
        print(f"{name:>26}: err={err:.6f}  bits/elem={info['bits_per_elem']:.3f}")
    bare = float_quantize(W, 2, 1).astype(np.float64)
    out["bare_E2M1"] = rel_l2_error(W, bare)
    print(f"{'裸 E2M1（无 block scale）':>26}: err={out['bare_E2M1']:.6f}  bits/elem=4.000")

    X = smooth.make_outlier_activations(512, 256, n_outliers=4, outlier_scale=2000.0, seed=4)
    out["act_e4m3"] = rel_l2_error(X, float_quantize(X, 4, 3).astype(np.float64))
    out["act_e5m2"] = rel_l2_error(X, float_quantize(X, 5, 2).astype(np.float64))
    Xn = smooth.make_outlier_activations(512, 256, n_outliers=0, seed=4)
    out["act_e4m3_noout"] = rel_l2_error(Xn, float_quantize(Xn, 4, 3).astype(np.float64))
    out["act_e5m2_noout"] = rel_l2_error(Xn, float_quantize(Xn, 5, 2).astype(np.float64))
    print("=== FP8 格式对比（激活, 离群通道 ×2000 vs 无离群, rel L2）===")
    print(f"有离群(×2000): E4M3={out['act_e4m3']:.6f}  E5M2={out['act_e5m2']:.6f}")
    print(f"无离群        : E4M3={out['act_e4m3_noout']:.6f}  E5M2={out['act_e5m2_noout']:.6f}")
    print("读法：E4M3 精度高但动态范围小（±448），遇大离群通道被饱和拖垮；E5M2 范围大")
    print("      （±57344）但尾数少 1 位，对离群鲁棒、典型值误差大——按数据特性分域选择。")
    return out


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

_SCENARIOS = [
    ("linear_quant", scenario_linear_quant),
    ("group_tradeoff", scenario_group_tradeoff),
    ("smooth_quant", scenario_smooth_quant),
    ("gptq_vs_rtn", scenario_gptq_vs_rtn),
    ("kv_long_context", scenario_kv_long_context),
    ("fp4_fp8_formats", scenario_fp4_fp8_formats),
]


def run_demo() -> dict:
    print("模型量化与压缩基础设施 Mini Demo\n" + "=" * 50)
    all_results = {}
    for name, fn in _SCENARIOS:
        all_results[name] = fn()
        print()
    return all_results


if __name__ == "__main__":
    run_demo()
