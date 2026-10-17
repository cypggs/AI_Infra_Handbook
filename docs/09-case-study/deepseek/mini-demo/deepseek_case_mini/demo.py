"""demo.py：5 个端到端场景，串起 DeepSeek 训练系统核心机制的"数字账"。

场景 1  流水线气泡：DualPipe vs 1F1B（技术报告 Table 2 闭式 + 调度器复现）
场景 2  FP8 精度：tensor-wise vs 1x128 tile-wise × FP32/FP16 累加
场景 3  EP all-to-all：通信量、NVLink/IB 拆分、节点受限路由、负载不均
场景 4  MLA：KV cache 压缩比与 DSA top-K 稀疏注意力的 FLOPs 比例
场景 5  一步训练的时间账：为什么 DeepSeek 敢不用 TP、敢跨节点放 EP

运行：python -m deepseek_case_mini.demo
"""
from __future__ import annotations

import numpy as np

from . import ep as ep_mod
from . import mla as mla_mod
from .fp8 import (
    bf16_reference_gemm,
    bulk_signal_error,
    channel_outlier_indices,
    fp8_gemm_simulate,
    make_channel_outlier_matrix,
    quantize_tensor_wise,
    quantize_tile_wise,
    relative_error,
)
from .pipeline import (
    ascii_timeline,
    bubble_1f1b,
    bubble_dualpipe,
    bubble_reduction_ratio,
    simulate_pipeline,
)

# ---------------------------------------------------------------------------
# 场景 1：DualPipe vs 1F1B
# ---------------------------------------------------------------------------

# V3 训练：PP=16；取 F=1 个时间单位，反向约为前向 2 倍 ⇒ B=2；
# W 为流水间通信（被 DualPipe 重叠的部分），取 0.2（可完全盖住）
_DEMO_PP = 16
_DEMO_F = 1.0
_DEMO_B = 2.0
_DEMO_W = 0.2
_DEMO_MICROBATCHES = 24  # 甘特图用的少量 micro-batch


def scenario_pipeline() -> dict:
    """DualPipe 相对 1F1B 的气泡缩减（闭式公式，来源 Table 2）。"""
    b_1f1b = bubble_1f1b(_DEMO_PP, _DEMO_F, _DEMO_B)
    b_dp = bubble_dualpipe(_DEMO_PP, _DEMO_F, _DEMO_B, _DEMO_W)
    ratio = bubble_reduction_ratio(_DEMO_PP, _DEMO_F, _DEMO_B, _DEMO_W)
    # 调度器复现 1F1B 的填充段：(PP-1)·F 的预热（M >> PP 时 dominates）
    sim = simulate_pipeline(
        pp=_DEMO_PP, num_microbatches=_DEMO_MICROBATCHES, f=_DEMO_F, b=_DEMO_B
    )
    return {
        "pp": _DEMO_PP,
        "bubble_1f1b": b_1f1b,
        "bubble_dualpipe": b_dp,
        "reduction_ratio": ratio,
        "sim_makespan": sim.makespan,
        "sim_bubble": sim.bubble,
        "sim_timeline": ascii_timeline(sim, _DEMO_PP),
    }


# ---------------------------------------------------------------------------
# 场景 2：FP8 精度账
# ---------------------------------------------------------------------------

_DEMO_M = 256
_DEMO_K = 4096  # 大 K ⇒ 累加步数多，累加策略差异可测
_DEMO_N = 256
# 离群通道强度扫描：演示"动态范围"问题——tensor-wise 在极端动态范围下
# 把主体压入 E4M3 次正规区而失真，tile-wise 把损伤隔离在离群通道所在组
_DEMO_OUTLIER_STD_SWEEP = (1.0, 1000.0, 30000.0, 100000.0)


def scenario_fp8(seed: int = 0) -> dict:
    """三部分精度账（口径各自独立，见 07 章说明）：

    1. bulk_sweep：主体信号（剔除离群通道）的量化误差随离群幅度的变化
       ——tensor-wise 把主体压入 E4M3 低bit区而崩溃，tile-wise 把损伤
       隔离在离群通道所在组（细粒度缩放的动机，V3 §3.3）；
    2. quant_floor：高斯权重上 E4M3 单次量化的固有误差（~3.6% RMS），
       这是 3 位尾数的格式属性，与缩放策略无关；
    3. accum_delta_fp16：FP16 直接累加相对 FP32 提升累加的额外误差
       （V3 每 128 元素提升 CUDA Core FP32 的对比组）。
    """
    # 1) 主体信号保真度扫描
    bulk_sweep = {}
    for os in _DEMO_OUTLIER_STD_SWEEP:
        x = make_channel_outlier_matrix(
            512, 1024, outlier_std=os, seed=seed
        )
        idx = channel_outlier_indices(1024, 8, seed)
        bulk_sweep[os] = {
            "tensor_wise": bulk_signal_error(
                x, quantize_tensor_wise(x), idx
            ),
            "tile_wise": bulk_signal_error(x, quantize_tile_wise(x), idx),
        }

    # 2) 量化误差 floor（高斯数据，量化后精确相乘；B 按 128x1 分组）
    rng = np.random.default_rng(seed + 1)
    a = rng.standard_normal((_DEMO_M, _DEMO_K))
    b = rng.standard_normal((_DEMO_K, _DEMO_N))
    ref = bf16_reference_gemm(a, b)
    err_tile = relative_error(
        quantize_tile_wise(a) @ quantize_tile_wise(b.T).T, ref
    )
    err_tensor = relative_error(
        quantize_tensor_wise(a) @ quantize_tensor_wise(b.T).T, ref
    )

    # 3) 累加策略对比（同一量化输入，只变累加器）
    gemm_fp32 = fp8_gemm_simulate(a, b, accumulate="fp32")
    gemm_fp16 = fp8_gemm_simulate(a, b, accumulate="fp16")
    accum_delta = relative_error(gemm_fp16, gemm_fp32)

    return {
        "bulk_sweep": bulk_sweep,
        "quant_floor_tile": err_tile,
        "quant_floor_tensor": err_tensor,
        "accum_delta_fp16": accum_delta,
    }


# ---------------------------------------------------------------------------
# 场景 3：EP all-to-all 通信账（V3 风格配置）
# ---------------------------------------------------------------------------

# 每个 micro-batch 单卡 token 数：V3 全局 batch ≈ 262K tokens、DP=32
_DEMO_TOKENS_PER_GPU = 8192


def scenario_ep(seed: int = 0) -> dict:
    """EP64（8 节点）下，节点受限路由与负载不均对通信时间的影响。"""
    cfg_limited = ep_mod.EpConfig()  # 默认 V3 配置：M=4 节点受限
    cfg_unlimited = ep_mod.EpConfig(nodes_limited=None)

    dispatch = ep_mod.dispatch_bytes_per_gpu(_DEMO_TOKENS_PER_GPU, cfg_limited)
    t_limited = ep_mod.all_to_all_time(
        dispatch, cfg_limited, imbalance=ep_mod.routing_imbalance(
            _DEMO_TOKENS_PER_GPU, cfg_limited, seed
        )
    )
    t_unlimited = ep_mod.all_to_all_time(
        dispatch, cfg_unlimited, imbalance=ep_mod.routing_imbalance(
            _DEMO_TOKENS_PER_GPU, cfg_unlimited, seed
        )
    )
    nv, ib = ep_mod.split_traffic(dispatch, cfg_limited)
    return {
        "tokens_per_gpu": _DEMO_TOKENS_PER_GPU,
        "dispatch_bytes": dispatch,
        "nvlink_bytes": nv,
        "ib_bytes": ib,
        "seconds_limited": t_limited,
        "seconds_unlimited": t_unlimited,
        "speedup_node_limited": t_unlimited / t_limited,
    }


# ---------------------------------------------------------------------------
# 场景 4：MLA 压缩比 + DSA 稀疏比例
# ---------------------------------------------------------------------------


def scenario_mla() -> dict:
    """V3 真实维度下的 KV cache 压缩比与 V3.2 稀疏注意力的计算比例。"""
    cfg = mla_mod.v3_reference_config()
    cache = mla_mod.kv_cache_bytes_per_token(cfg)
    err_clean = mla_mod.latent_reconstruction_error(noise=0.0)
    err_noisy = mla_mod.latent_reconstruction_error(noise=0.05)
    flops_ratio = mla_mod.sparse_attention_flops_ratio(
        seq_len=128 * 1024, top_k=2048
    )
    return {
        "v3_mha_bytes_per_token": cache["mha"],
        "v3_mla_bytes_per_token": cache["mla"],
        "compression_ratio": cache["compression_ratio"],
        "recon_error_clean": err_clean,
        "recon_error_noisy": err_noisy,
        "dsa_flops_ratio": flops_ratio,
    }


# ---------------------------------------------------------------------------
# 场景 5：一步训练的时间账
# ---------------------------------------------------------------------------

# 官方口径：每 1T tokens 消耗 180K H800 GPU 小时（技术报告 Table 1）
_GPU_SECONDS_PER_TOKEN = 180_000 * 3600 / 1e12
# 一个优化器 step 的 micro-batch 数（示意：DP=32、全局 batch ≈ 32×8192×... 的尺度）
_MICROBATCHES_PER_STEP = 32


def scenario_step_budget(seed: int = 0) -> dict:
    """把场景 1/3 的账和官方算力账拼成一个优化器 step 的时间预算。

    两条结论（V3 技术报告 §3.2 的底气）：
    1. 计算/通信比 ~140×：all-to-all 每 token 通信 ~0.0045 ms，而单 token
       计算 ~0.648 ms（官方口径）——通信可以被 DualPipe 的 overlap
       完全盖住 ⇒ 不需要 TP、EP 可以跨节点细粒度切分；
    2. 一个 32-micro-batch 的 step：1F1B 气泡 45 单位 ≈ 80 s（占 32%），
       DualPipe 降到 16.8 单位 ≈ 30 s（占 15%）——省下的近 50 s/step
       就是"两个月训完 V3"的工程来源之一。
    """
    compute_ms = _GPU_SECONDS_PER_TOKEN * 1000.0 * _DEMO_TOKENS_PER_GPU
    ep = scenario_ep(seed)
    # 每 token 通信时间：dispatch 时间 / 单卡 token 数（combine 对称，×2）
    comm_ms = ep["seconds_limited"] * 1000.0 / _DEMO_TOKENS_PER_GPU * 2.0

    # 气泡折算：单个 micro-batch 计算 = F+B = 3 个时间单位
    unit_ms = compute_ms / 3.0
    bubble_1f1b_ms = 45.0 * unit_ms  # (PP-1)(F+B), PP=16
    bubble_dp_ms = 16.8 * unit_ms  # (PP/2-1)(F+B-3W), W=0.2
    total_1f1b_ms = _MICROBATCHES_PER_STEP * compute_ms + bubble_1f1b_ms
    total_dp_ms = _MICROBATCHES_PER_STEP * compute_ms + bubble_dp_ms

    return {
        "compute_ms_per_microbatch": compute_ms,
        "ep_comm_ms_per_token": comm_ms,
        "compute_to_comm_ratio": compute_ms / max(comm_ms * _DEMO_TOKENS_PER_GPU, 1e-12),
        "bubble_1f1b_ms": bubble_1f1b_ms,
        "bubble_dualpipe_ms": bubble_dp_ms,
        "bubble_ratio_1f1b": bubble_1f1b_ms / total_1f1b_ms,
        "bubble_ratio_dualpipe": bubble_dp_ms / total_dp_ms,
        "step_time_saved_ms": bubble_1f1b_ms - bubble_dp_ms,
    }


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 72)
    print("场景 1：DualPipe vs 1F1B 流水线气泡（PP=16, F=1, B=2, W=0.2）")
    print("=" * 72)
    s1 = scenario_pipeline()
    print(f"1F1B   气泡（Table 2 闭式）: {s1['bubble_1f1b']:.1f} 时间单位")
    print(f"DualPipe 气泡（Table 2 闭式）: {s1['bubble_dualpipe']:.1f} 时间单位")
    print(f"气泡缩减比: {s1['reduction_ratio'] * 100:.1f}%")
    print(f"列表调度器复现 1F1B：makespan={s1['sim_makespan']:.1f}, "
          f"数值气泡={s1['sim_bubble']:.1f}")
    print()
    print(s1["sim_timeline"])
    print()

    print("=" * 72)
    print("场景 2：FP8 精度账（动态范围扫描 + 累加策略）")
    print("=" * 72)
    s2 = scenario_fp8()
    print("主体信号保真度扫描（剔除离群通道后的相对量化误差）:")
    print(f"  {'离群 std':>10} | {'tensor-wise':>12} | {'1x128 tile-wise':>15}")
    for os, row in s2["bulk_sweep"].items():
        print(f"  {os:>10.0f} | {row['tensor_wise'] * 100:>11.2f}% | {row['tile_wise'] * 100:>14.2f}%")
    print(f"高斯数据单次量化误差 floor: tile-wise {s2['quant_floor_tile'] * 100:.2f}%, "
          f"tensor-wise {s2['quant_floor_tensor'] * 100:.2f}%（同为 E4M3 格式属性）")
    print(f"FP16 直接累加的额外误差（对照 FP32 提升）: {s2['accum_delta_fp16'] * 100:.4f}%")
    print("注：V3 附录 B 的 <0.25% 是 FP8 vs BF16 的端到端【损失误差】口径。")
    print()

    print("=" * 72)
    print("场景 3：EP64 all-to-all 通信账（V3 风格：8192 tokens/GPU, top-8, hidden 7168）")
    print("=" * 72)
    s3 = scenario_ep()
    print(f"dispatch 总量: {s3['dispatch_bytes'] / 1e6:.1f} MB/GPU")
    print(f"  其中 NVLink（组内 8 卡）: {s3['nvlink_bytes'] / 1e6:.1f} MB")
    print(f"  其中 IB（跨节点）:       {s3['ib_bytes'] / 1e6:.1f} MB")
    print(f"节点受限路由(M=4)通信时间: {s3['seconds_limited'] * 1000:.2f} ms")
    print(f"不限节点(M=8)通信时间:     {s3['seconds_unlimited'] * 1000:.2f} ms")
    print(f"节点受限带来的加速: {s3['speedup_node_limited']:.2f}x")
    print()

    print("=" * 72)
    print("场景 4：MLA 压缩比 + DSA 稀疏注意力（V3/V3.2 真实维度）")
    print("=" * 72)
    s4 = scenario_mla()
    print(f"V3 MHA 假设下 KV/token/层: {s4['v3_mha_bytes_per_token'] / 1024:.1f} KiB")
    print(f"V3 MLA 实际 KV/token/层:   {s4['v3_mla_bytes_per_token'] / 1024:.2f} KiB")
    print(f"压缩比: {s4['compression_ratio']:.1f}x")
    print(f"潜空间重建误差（无噪声）: {s4['recon_error_clean']:.2e}")
    print(f"潜空间重建误差（5% 噪声）: {s4['recon_error_noisy']:.2e}")
    print(f"V3.2 DSA 主注意力 FLOPs 比例 (k/L=2048/128K): {s4['dsa_flops_ratio']:.4f}")
    print()

    print("=" * 72)
    print("场景 5：一个优化器 step 的时间账（为什么不用 TP、EP 敢跨节点）")
    print("=" * 72)
    s5 = scenario_step_budget()
    print(f"单卡 micro-batch 计算时间: {s5['compute_ms_per_microbatch']:.0f} ms"
          f"（{_DEMO_TOKENS_PER_GPU} tokens × 0.648 ms/token 官方口径）")
    print(f"all-to-all 每 token 通信时间: {s5['ep_comm_ms_per_token']:.4f} ms"
          f"（dispatch+combine）")
    print(f"计算/通信比: {s5['compute_to_comm_ratio']:.0f}x")
    print(f"32-micro-batch step：1F1B 气泡 {s5['bubble_1f1b_ms'] / 1000:.1f} s"
          f"（占 {s5['bubble_ratio_1f1b'] * 100:.1f}%）")
    print(f"32-micro-batch step：DualPipe 气泡 {s5['bubble_dualpipe_ms'] / 1000:.1f} s"
          f"（占 {s5['bubble_ratio_dualpipe'] * 100:.1f}%）")
    print(f"DualPipe 每 step 省下的时间: {s5['step_time_saved_ms'] / 1000:.1f} s")
    print()
    print("核心结论：通信可以被计算完全盖住 ⇒ 省掉 TP、EP 跨节点、气泡近零。")


if __name__ == "__main__":
    main()
