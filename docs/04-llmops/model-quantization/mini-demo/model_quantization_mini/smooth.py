"""SmoothQuant 风格「难度迁移」逐通道缩放（纯 numpy、确定性）。

SmoothQuant（Xiao et al., 2022）观察：LLM 激活有少数「离群通道」
（outlier channels），幅度比典型值大几十倍，导致激活量化极难；
而权重分布平滑、容易量化。于是引入逐输入通道缩放 s：

    X' = X / s,  W' = W · diag(s)  ⇒  X'W'ᵀ ≡ XWᵀ（数学等价）

s_j = max|X_j|^α / max|W_j|^(1-α)：α 控制难度迁移方向——
α→1 把难度全推给权重，α→0 全推给激活，α=0.5 均衡。
迁移后两者都「变乖」，per-tensor INT8（W8A8）的量化误差大幅下降。
"""

from __future__ import annotations

import numpy as np

from .quantize import QuantConfig, quantize_tensor, rel_l2_error


def compute_smooth_scales(
    W: np.ndarray, X: np.ndarray, alpha: float = 0.5
) -> np.ndarray:
    """计算逐输入通道的平滑缩放向量 s (in_dim,)。"""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha 必须在 [0, 1]")
    W = np.asarray(W, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    w_max = np.max(np.abs(W), axis=0)
    x_max = np.max(np.abs(X), axis=0)
    eps = 1e-8
    return (x_max + eps) ** alpha / (w_max + eps) ** (1.0 - alpha)


def apply_smoothing(
    W: np.ndarray, X: np.ndarray, s: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """应用缩放：W' = W·diag(s)，X' = X/diag(s)。数学上与原乘积等价。"""
    W = np.asarray(W, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    return W * s[None, :], X / s[None, :]


def per_tensor_int8(x: np.ndarray) -> np.ndarray:
    """per-tensor 对称 INT8 量化再反量化（模拟 SmoothQuant 的硬件路径）。"""
    qt = quantize_tensor(
        x, QuantConfig(bits=8, symmetric=True, granularity="per_tensor")
    )
    return qt.dequant()


def linear_output(
    X: np.ndarray, W: np.ndarray, quantize: bool = False
) -> np.ndarray:
    """线性层输出 XWᵀ；quantize=True 时对输入和权重各做 per-tensor INT8。"""
    X = np.asarray(X, dtype=np.float64)
    W = np.asarray(W, dtype=np.float64)
    if quantize:
        X = per_tensor_int8(X)
        W = per_tensor_int8(W)
    return X @ W.T


def smoothed_quant_error(
    W: np.ndarray, X: np.ndarray, alpha: float = 0.5
) -> dict:
    """对比未迁移 vs 迁移后的 per-tensor INT8 输出误差。

    返回 dict：baseline_err、smoothed_err、reduction_factor、scales。
    """
    W = np.asarray(W, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    ref = linear_output(X, W)
    base = linear_output(X, W, quantize=True)
    s = compute_smooth_scales(W, X, alpha)
    W_s, X_s = apply_smoothing(W, X, s)
    smooth = linear_output(X_s, W_s, quantize=True)
    e_base = rel_l2_error(ref, base)
    e_smooth = rel_l2_error(ref, smooth)
    return {
        "alpha": alpha,
        "baseline_err": e_base,
        "smoothed_err": e_smooth,
        "reduction_factor": e_base / e_smooth if e_smooth > 0 else float("inf"),
        "scales": s,
    }


def alpha_sweep(W: np.ndarray, X: np.ndarray, alphas: tuple = (0.0, 0.25, 0.5, 0.75, 1.0)) -> list[dict]:
    """扫一组 α，返回每个 α 的误差信息（用于找最优迁移比例）。"""
    return [smoothed_quant_error(W, X, a) for a in alphas]


def make_outlier_activations(
    n_samples: int,
    in_dim: int,
    n_outliers: int = 4,
    outlier_scale: float = 30.0,
    seed: int = 1,
) -> np.ndarray:
    """构造含少数离群通道的激活（模拟 LLM 激活的 outlier 现象）。"""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_samples, in_dim))
    out_idx = rng.choice(in_dim, size=min(n_outliers, in_dim), replace=False)
    X[:, out_idx] *= outlier_scale
    return X
