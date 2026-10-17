"""fp8.py：FP8（E4M3）量化 / 反量化与累加精度模拟。

复现 DeepSeek-V3 技术报告 §3.3 的三个关键决策的教育版模型：

1. **细粒度缩放（fine-grained quantization）**：不是整个张量一个缩放因子
   （tensor-wise），而是前向按 1x128（行内每 128 个元素一组）、反向按 128x1
   分组（tile-wise / block-wise），每组独立 amax 缩放，缓解特征离群值
   （outlier）对动态范围的挤占。
2. **高精度累加（increasing accumulation precision）**：模拟 FP8 张量核
   每 N_C=128 个元素（4 条 WGMMA）把部分和提升到 CUDA Core FP32 累加，
   对比"全程 FP16/BF16 累加"的误差——这是 FP8 训练在 H800 上跑通的精度关键。
3. **全 E4M3（mantissa over exponents）**：前向、反向梯度统一 E4M3，
   不采用 E4M3/E5M2 混合格式，靠细粒度缩放换取精度。

所有计算纯 numpy、确定性（调用方负责 seed），可在 CPU 上运行。
"""
from __future__ import annotations

import numpy as np

# E4M3（fn 变体）：4 位指数（bias=7）、3 位尾数；最大正规数 448，
# 最小正规数 2^-6，次正规数步长 2^-9；无 Inf（ saturating 语义）。
E4M3_MAX = 448.0
E4M3_MIN_NORMAL = 2.0**-6
E4M3_SUBNORMAL_STEP = 2.0**-9


def quantize_e4m3(x: np.ndarray) -> np.ndarray:
    """把浮点数组四舍五入（RNE）到 E4M3 网格，越界值饱和到 ±448。

    用 frexp 分解实现，不依赖 GPU：
      - 正规区间 [2^-6, 448]：尾数 3 位 ⇒ 量化步长 = 2^(e-4)，e 为 frexp 指数；
      - 次正规区间 [0, 2^-6)：固定步长 2^-9。
    """
    x = np.asarray(x, dtype=np.float64)
    sign = np.sign(x)
    a = np.abs(x)
    out = np.zeros_like(a)

    normal = a >= E4M3_MIN_NORMAL
    # 正规区间
    _, e = np.frexp(a[normal])  # a = m * 2**e, m in [0.5, 1)
    step = np.exp2(e - 4)  # 3 位尾数 ⇒ 16 个格点 per octave
    q = np.round(a[normal] / step) * step
    q = np.minimum(q, E4M3_MAX)
    out[normal] = q
    # 次正规区间
    if np.any(~normal):
        q_sub = np.round(a[~normal] / E4M3_SUBNORMAL_STEP) * E4M3_SUBNORMAL_STEP
        out[~normal] = np.minimum(q_sub, E4M3_MIN_NORMAL)
    return (sign * out).astype(np.float64)


def compute_scales(x: np.ndarray, group_size: int = 128) -> np.ndarray:
    """按组计算 amax 缩放因子：scale = amax / 448（DeepGEMM 布局为转置存储）。

    沿最后一维分组；最后一维不是 group_size 整数倍时末尾组按实际长度。
    返回与 x 同形状的每元素缩放因子（ broadcasting 到组内每个元素）。
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    if n % group_size != 0:
        raise ValueError(f"最后一维 {n} 必须能被 group_size={group_size} 整除")
    grouped = x.reshape(*x.shape[:-1], n // group_size, group_size)
    amax = np.abs(grouped).max(axis=-1, keepdims=True)
    amax = np.maximum(amax, 1e-12)  # 全零组防除零
    scale = amax / E4M3_MAX
    return np.broadcast_to(scale, grouped.shape).reshape(x.shape)


def quantize_with_scale(x: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """x / scale 后量化到 E4M3，再乘回 scale（反量化值）。"""
    q = quantize_e4m3(np.asarray(x, dtype=np.float64) / scale)
    return q * scale


def quantize_tile_wise(x: np.ndarray, group_size: int = 128) -> np.ndarray:
    """DeepSeek-V3 前向路径的 1x128 细粒度量化模拟。"""
    return quantize_with_scale(x, compute_scales(x, group_size))


def quantize_tensor_wise(x: np.ndarray) -> np.ndarray:
    """对照组：整个张量单一 amax 缩放（tensor-wise）。"""
    x = np.asarray(x, dtype=np.float64)
    amax = max(np.abs(x).max(), 1e-12)
    scale = np.full_like(x, amax / E4M3_MAX)
    return quantize_with_scale(x, scale)


def fp8_gemm_simulate(
    a: np.ndarray,
    b: np.ndarray,
    group_size: int = 128,
    accumulate: str = "fp32",
    promote_every: int = 128,
) -> np.ndarray:
    """模拟 FP8 GEMM：A(M,K) @ B(K,N)。

    - A 按行分组（1x128）量化，B 按列分组（128x1，对 B.T 按行分组）量化；
    - 组内乘积在"张量核"中以高精度求和（模拟 FP32 部分和）；
    - 每 promote_every 个 K 元素把部分和并入累加器：
      accumulate="fp32" 模拟提升到 CUDA Core FP32 累加（V3 做法），
      accumulate="fp16" 模拟用 FP16 直接累加（对照，误差更大）。
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    m, k = a.shape
    k2, n = b.shape
    if k != k2:
        raise ValueError("A 的 K 维与 B 的 K 维不一致")
    if k % group_size != 0:
        raise ValueError("K 必须能被 group_size 整除")

    aq = quantize_tile_wise(a, group_size)
    bq = quantize_tile_wise(b.T, group_size).T

    acc_dtype = np.float32 if accumulate == "fp32" else np.float16
    acc = np.zeros((m, n), dtype=acc_dtype)
    for k0 in range(0, k, promote_every):
        k1 = min(k0 + promote_every, k)
        # 张量核内部：组内乘加按高精度完成
        part = aq[:, k0:k1] @ bq[k0:k1, :]
        # 提升 / 直接累加
        acc = (acc.astype(np.float64) + part.astype(np.float64)).astype(acc_dtype)
    return acc.astype(np.float64)


def relative_error(approx: np.ndarray, ref: np.ndarray) -> float:
    """相对 Frobenius 误差 ||approx - ref|| / ||ref||。"""
    approx = np.asarray(approx, dtype=np.float64)
    ref = np.asarray(ref, dtype=np.float64)
    denom = np.linalg.norm(ref)
    if denom == 0.0:
        raise ValueError("参考值全零，无法计算相对误差")
    return float(np.linalg.norm(approx - ref) / denom)


def bf16_reference_gemm(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """BF16 GEMM 参考：先把输入舍入到 BF16 网格，再在 float64 中计算。"""
    a64 = np.asarray(a, dtype=np.float64)
    b64 = np.asarray(b, dtype=np.float64)

    def to_bf16(x: np.ndarray) -> np.ndarray:
        u = x.astype(np.float32).view(np.uint32)
        rounded = ((u + 0x7FFF + ((u >> 16) & 1)) >> 16) << 16
        return rounded.astype(np.uint32).view(np.float32).astype(np.float64)

    return to_bf16(a64) @ to_bf16(b64)


def channel_outlier_indices(
    cols: int, n_outlier_cols: int = 8, seed: int = 0
) -> np.ndarray:
    """确定性选择离群通道的列号（与 make_channel_outlier_matrix 内部一致）。"""
    rng = np.random.default_rng(seed)
    return rng.choice(cols, size=min(n_outlier_cols, cols), replace=False)


def make_channel_outlier_matrix(
    rows: int,
    cols: int,
    n_outlier_cols: int = 8,
    outlier_std: float = 1.0,
    seed: int = 0,
) -> np.ndarray:
    """构造带"离群通道"的矩阵：大部分列 N(0,1)，少数列 std=outlier_std。

    模拟 LLM 激活的经典形态——个别通道的幅度比主体高几个数量级。
    这是 tensor-wise 缩放失效、需要 tile-wise 细粒度缩放的原因：
    全局 amax 被离群通道主导后，主体元素被压到 E4M3 低bit区/次正规区，
    相对误差爆炸；而按 128 元素分组后，离群通道只影响它所在的那一组。
    """
    rng = np.random.default_rng(seed + 1)
    x = rng.standard_normal((rows, cols))
    idx = channel_outlier_indices(cols, n_outlier_cols, seed)
    x[:, idx] = rng.standard_normal((rows, len(idx))) * outlier_std
    return x


def quantization_snr(x: np.ndarray, q: np.ndarray) -> float:
    """量化信噪比 ||x|| / ||x - q||（越大越好）。"""
    x = np.asarray(x, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    noise = np.linalg.norm(x - q)
    if noise == 0.0:
        return float("inf")
    return float(np.linalg.norm(x) / noise)


def bulk_signal_error(
    x: np.ndarray, q: np.ndarray, exclude_cols: np.ndarray
) -> float:
    """主体信号的保真误差：剔除离群列后 ||bulk - q_bulk|| / ||bulk||。

    离群通道占比小、能量大，全张量 SNR 会被它主导而掩盖主体失真；
    衡量主体（占绝大多数的元素）才能看出 tensor-wise 在极端动态范围下
    把主体压入低bit区的损伤。
    """
    x = np.asarray(x, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    mask = np.ones(x.shape[1], dtype=bool)
    mask[np.asarray(exclude_cols, dtype=int)] = False
    bulk, q_bulk = x[:, mask], q[:, mask]
    denom = np.linalg.norm(bulk)
    if denom == 0.0:
        raise ValueError("主体信号全零")
    return float(np.linalg.norm(bulk - q_bulk) / denom)
