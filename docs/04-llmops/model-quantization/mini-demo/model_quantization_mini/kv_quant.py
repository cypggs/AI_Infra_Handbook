"""KV cache 分组量化与注意力误差传播模拟（纯 numpy、确定性）。

对应 KIVI（Liu et al., 2024）等研究的两个核心观察：

1. Key 的「离群」体现在通道维（某些 channel 全序列都很大）→
   应按通道（跨 token）分组量化；按 token 分组会被离群通道拖垮 scale；
2. Value 的误差直接进入输出残差流 → 按 token 分组即可，且误差
   不会随上下文长度爆炸（softmax 对 score 误差有压缩作用）。

模块用一个小注意力模拟验证：量化 K/V 后计算 attention(Q,K,V)，
度量输出相对 FP 基准的余弦相似度与最大误差，并观察误差随上下文
长度的增长规律。
"""

from __future__ import annotations

import numpy as np

from .quantize import QuantConfig, quantize_tensor


def _group_quant_along(x: np.ndarray, bits: int, group_size: int, axis: int) -> np.ndarray:
    """沿 axis 分组的 group-wise 对称量化再反量化。"""
    qt = quantize_tensor(
        x,
        QuantConfig(
            bits=bits,
            symmetric=True,
            granularity="group_wise",
            group_size=group_size,
            axis=axis,
        ),
    )
    return qt.dequant()


def quantize_keys(K: np.ndarray, bits: int, group_size: int, mode: str) -> np.ndarray:
    """量化 Key cache (T, d)。

    mode="channel"：按通道分组（组沿 token 轴 T 切，等价 KIVI 的 per-channel）；
    mode="token"  ：按 token 分组（组沿特征轴 d 切）。
    """
    if mode == "channel":
        return _group_quant_along(K, bits, group_size, axis=0)
    if mode == "token":
        return _group_quant_along(K, bits, group_size, axis=1)
    raise ValueError("mode 必须是 'channel' 或 'token'")


def quantize_values(V: np.ndarray, bits: int, group_size: int) -> np.ndarray:
    """量化 Value cache (T, d)（按 token 分组，即沿特征轴 d）。"""
    return _group_quant_along(V, bits, group_size, axis=1)


def attention(Q: np.ndarray, K: np.ndarray, V: np.ndarray) -> np.ndarray:
    """缩放点积注意力。Q (q_len, d)，K/V (T, d)。"""
    Q = np.asarray(Q, dtype=np.float64)
    K = np.asarray(K, dtype=np.float64)
    V = np.asarray(V, dtype=np.float64)
    d = K.shape[1]
    scores = Q @ K.T / np.sqrt(d)
    scores = scores - scores.max(axis=-1, keepdims=True)  # 数值稳定 softmax
    exp = np.exp(scores)
    attn = exp / exp.sum(axis=-1, keepdims=True)
    return attn @ V


def kv_quant_attention_error(
    Q: np.ndarray,
    K: np.ndarray,
    V: np.ndarray,
    bits: int,
    group_size: int = 32,
    k_mode: str = "channel",
) -> dict:
    """量化 K/V 后做一次注意力，返回相对 FP 基准的输出误差指标。"""
    ref = attention(Q, K, V)
    K_q = quantize_keys(K, bits, group_size, k_mode)
    V_q = quantize_values(V, bits, group_size)
    out = attention(Q, K_q, V_q)
    num = np.linalg.norm(out - ref, axis=-1)
    den = np.linalg.norm(ref, axis=-1)
    cos = np.zeros(Q.shape[0])
    for i in range(Q.shape[0]):
        a, b = ref[i], out[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        cos[i] = 0.0 if na == 0 or nb == 0 else float(a @ b / (na * nb))
    return {
        "cosine": float(np.mean(cos)),
        "rel_l2_rows": float(np.mean(num / np.maximum(den, 1e-12))),
        "max_abs_err": float(np.max(np.abs(out - ref))),
    }


def error_vs_context_length(
    rng: np.random.Generator,
    lengths: tuple = (128, 256, 384, 512),
    d: int = 64,
    bits: int = 4,
    group_size: int = 32,
    k_mode: str = "channel",
    n_queries: int = 8,
) -> dict[int, dict]:
    """对多个上下文长度构造 K/V（每个长度用固定种子的确定性数据），
    返回每个长度的量化注意力误差。"""
    results: dict[int, dict] = {}
    for T in lengths:
        K, V = make_kv_cache(T, d, outlier_channels=4, outlier_scale=20.0, seed=T)
        Q = rng.standard_normal((n_queries, d))
        results[T] = kv_quant_attention_error(Q, K, V, bits, group_size, k_mode)
    return results


def make_kv_cache(
    n_tokens: int,
    head_dim: int,
    outlier_channels: int = 4,
    outlier_scale: float = 20.0,
    seed: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """构造含通道离群的确定性 K/V（T, d)。"""
    rng = np.random.default_rng(seed)
    K = rng.standard_normal((n_tokens, head_dim))
    V = rng.standard_normal((n_tokens, head_dim))
    if outlier_channels > 0:
        idx = rng.choice(head_dim, size=min(outlier_channels, head_dim), replace=False)
        K[:, idx] *= outlier_scale
    return K, V
