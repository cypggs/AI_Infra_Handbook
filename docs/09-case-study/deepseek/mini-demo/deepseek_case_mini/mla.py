"""mla.py：MLA（Multi-head Latent Attention）低秩 KV 压缩示意。

DeepSeek-V3 的核心显存/带宽决策：不为 128 个注意力头各存一份 K/V，
而是把每 token 的 K、V 压缩到一个 512 维共享潜向量 c_t（低秩投影），
推理时只对当前 query 在线展开成各头 K/V；再配一个 64 维的解耦 RoPE
 key k_R 保留位置信息（不做压缩）。

本模块用小维度矩阵演示三件事：

1. **压缩比**：per-token KV cache 从 MHA 的 2×n_heads×d_head 元素
   降到 n_latent + n_rope 元素（V3 配置下约 57×）；
2. **重建**： latent 向量经 up-projection 可还原各头 K/V（低秩重构
   误差可控），训练/推理数学上与 MHA 等价——压缩的是"存储与带宽"，
   不是模型表达能力；
3. **DSA 的伏笔**：潜向量维度低，使"lightning indexer + top-K 稀疏
   选择"（V3.2）能用极低代价在海量历史 token 上打分。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MlaConfig:
    """MLA 维度配置。"""

    n_heads: int = 16  # 演示用小头数（V3 是 128）
    d_head: int = 32  # 每头维度（V3 是 128）
    n_latent: int = 32  # KV 潜向量维度 c_t（V3 是 512）
    n_rope: int = 8  # 解耦 RoPE key 维度 k_R（V3 是 64）


def v3_reference_config() -> MlaConfig:
    """DeepSeek-V3 的 MLA 维度（技术报告 §2.1.1）。"""
    return MlaConfig(n_heads=128, d_head=128, n_latent=512, n_rope=64)


def kv_elements_mha(cfg: MlaConfig) -> int:
    """标准 MHA：每 token 每层的 KV 元素数 = 2(K,V) × 头数 × 头维度。"""
    return 2 * cfg.n_heads * cfg.d_head


def kv_elements_mla(cfg: MlaConfig) -> int:
    """MLA：每 token 每层的 KV 元素数 = 潜向量 + 解耦 RoPE key。"""
    return cfg.n_latent + cfg.n_rope


def kv_compression_ratio(cfg: MlaConfig) -> float:
    """压缩比 = MHA 元素数 / MLA 元素数。"""
    return kv_elements_mha(cfg) / kv_elements_mla(cfg)


def kv_cache_bytes_per_token(cfg: MlaConfig, dtype_bytes: int = 2) -> dict:
    """每 token 每层 KV cache 字节数的对照表。"""
    return {
        "mha": kv_elements_mha(cfg) * dtype_bytes,
        "mla": kv_elements_mla(cfg) * dtype_bytes,
        "compression_ratio": kv_compression_ratio(cfg),
    }


def make_mla_weights(cfg: MlaConfig, seed: int = 0):
    """构造演示用投影矩阵（确定性）。

    返回 dict：
      dkv   (d_model, n_latent)   token 表示 → 潜向量 c_t 的降维投影
      uk    (n_latent, n_heads*d_head)  潜向量 → 各头 K 的升维投影
      uv    (n_latent, n_heads*d_head)  潜向量 → 各头 V 的升维投影
    """
    rng = np.random.default_rng(seed)
    d_model = cfg.n_heads * cfg.d_head

    def orthoish(rows: int, cols: int) -> np.ndarray:
        # 两个高斯矩阵相乘 ⇒ 列空间近似随机低秩子空间，重建误差稳定
        return (rng.standard_normal((rows, d_model)) @ rng.standard_normal((d_model, cols))) / np.sqrt(d_model)

    return {
        "dkv": orthoish(cfg.n_latent, d_model).T,  # (d_model, n_latent)
        "uk": orthoish(cfg.n_latent, cfg.n_heads * cfg.d_head),
        "uv": orthoish(cfg.n_latent, cfg.n_heads * cfg.d_head),
    }


def compress_kv(h: np.ndarray, dkv: np.ndarray) -> np.ndarray:
    """token 表示 h (seq, d_model) → 潜向量 c (seq, n_latent)。"""
    return h @ dkv


def reconstruct_heads(c: np.ndarray, up: np.ndarray, cfg: MlaConfig) -> np.ndarray:
    """潜向量 → 各头矩阵 (seq, n_heads, d_head)，用于验证低秩可重建。"""
    seq = c.shape[0]
    out = (c @ up).reshape(seq, cfg.n_heads, cfg.d_head)
    return out


def latent_reconstruction_error(
    cfg: MlaConfig = MlaConfig(), seq: int = 64, seed: int = 0, noise: float = 0.05
) -> float:
    """端到端重建误差：潜向量→K 与 直接计算 K 的相对误差。

    构造"真实"K = h @ W_k + noise·E：主成分在潜空间内（低秩世界，
    可被 MLA 无损表示），再叠加少量满秩扰动 E 模拟真实模型的不完美。
    noise=0 时误差应接近 0（MLA 对潜空间内数据是无损表示）——
    这正是"压缩的是存储与带宽，不是表达能力"的定量说明。
    """
    rng = np.random.default_rng(seed)
    w = make_mla_weights(cfg, seed=seed)
    d_model = cfg.n_heads * cfg.d_head
    # 真值 K：h @ W_k，其中 W_k 的真实列空间就在潜空间内（低秩世界）
    w_k = w["dkv"] @ w["uk"]  # (d_model, n_heads*d_head)
    h = rng.standard_normal((seq, d_model))
    k_true = (h @ w_k).reshape(seq, cfg.n_heads, cfg.d_head)
    if noise > 0.0:
        e = rng.standard_normal(k_true.shape)
        k_true = k_true + noise * np.linalg.norm(k_true) / np.linalg.norm(e) * e
    c = compress_kv(h, w["dkv"])
    k_recon = reconstruct_heads(c, w["uk"], cfg)
    num = np.linalg.norm(k_recon - k_true)
    den = np.linalg.norm(k_true)
    return float(num / max(den, 1e-12))


# ---------------------------------------------------------------------------
# DSA 伏笔：lightning indexer 打分 + top-K 选择
# ---------------------------------------------------------------------------

def lightning_index_scores(
    q_latent: np.ndarray, k_latent: np.ndarray, head_weights: np.ndarray
) -> np.ndarray:
    """lightning indexer 的简化打分（V3.2 技术报告 §2.1）。

    q_latent (seq, d) 与 k_latent (seq, d) 都是低维潜向量（共享 MQA 式
    单头打分，计算量是稠密注意力的 d/d_attn 分之一）；再加每 query 的
    可学习权重 head_weights (seq,)：
        score[t, s] = relu(q_t · k_s) * w_t
    """
    logits = q_latent @ k_latent.T
    return np.maximum(logits, 0.0) * head_weights[:, None]


def select_top_k(scores: np.ndarray, top_k: int) -> np.ndarray:
    """每行（每个 query）选 top_k 个历史 token 的布尔掩码。"""
    seq = scores.shape[0]
    k = min(top_k, seq)
    mask = np.zeros_like(scores, dtype=bool)
    idx = np.argsort(-scores, axis=1)[:, :k]
    rows = np.arange(seq)[:, None]
    mask[rows, idx] = True
    return mask


def sparse_attention_flops_ratio(seq_len: int, top_k: int) -> float:
    """DSA 主注意力 FLOPs 比例：O(L·k) / O(L²) = k/L。

    V3.2 训练配置：128K 上下文、每 query 选 2048 个 KV ⇒ 1/64。
    （lightning indexer 本身仍是 O(L²)，但维度低得多——见 05 章。）
    """
    if seq_len <= 0:
        raise ValueError("seq_len 必须为正")
    return min(top_k, seq_len) / seq_len
