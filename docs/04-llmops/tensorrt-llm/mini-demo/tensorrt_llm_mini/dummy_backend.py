"""NumPy CPU backend for executing the mini engine graph."""
from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Basic ops
# ---------------------------------------------------------------------------
def lookup(token_ids: np.ndarray, table: np.ndarray) -> np.ndarray:
    """Token-id to embedding lookup."""
    return table[token_ids.astype(np.int64)]


def linear(x: np.ndarray, weight: np.ndarray, bias: np.ndarray | None = None) -> np.ndarray:
    """Fully-connected layer: x @ W.T + b."""
    out = x @ weight.T
    if bias is not None:
        out = out + bias
    return out


def gelu(x: np.ndarray) -> np.ndarray:
    """Approximate GELU activation."""
    c = math.sqrt(2.0 / math.pi)
    return 0.5 * x * (1.0 + np.tanh(c * (x + 0.044715 * x**3)))


def layer_norm(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """Simple layer norm without learnable affine parameters."""
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps)


def add(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a + b


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / np.sum(e, axis=axis, keepdims=True)


# ---------------------------------------------------------------------------
# Attention with KV cache
# ---------------------------------------------------------------------------
def _split_qkv(qkv: np.ndarray, num_heads: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split concatenated QKV into (batch, seq, heads, head_dim) arrays."""
    b, s, three_h = qkv.shape
    h = three_h // 3
    head_dim = h // num_heads
    q, k, v = np.split(qkv, 3, axis=-1)
    q = q.reshape(b, s, num_heads, head_dim).transpose(0, 2, 1, 3)
    k = k.reshape(b, s, num_heads, head_dim).transpose(0, 2, 1, 3)
    v = v.reshape(b, s, num_heads, head_dim).transpose(0, 2, 1, 3)
    return q, k, v


def attention(
    qkv: np.ndarray,
    num_heads: int,
    kv_cache: Dict[str, np.ndarray | int],
) -> Tuple[np.ndarray, Dict[str, np.ndarray | int]]:
    """Single-sequence causal self-attention using a KV cache.

    ``kv_cache`` contains ``cache_k``, ``cache_v`` (num_heads, max_seq, head_dim)
    and ``cache_len`` (int).  The cache is updated in place.
    """
    cache_k = kv_cache["cache_k"]
    cache_v = kv_cache["cache_v"]
    cache_len = int(kv_cache["cache_len"])

    q, k, v = _split_qkv(qkv, num_heads)
    b, nh, s, hd = q.shape
    assert b == 1, "this backend supports single-sequence execution per call"

    scale = 1.0 / math.sqrt(hd)

    if s > 1:
        # Prefill: causal self-attention over the current chunk.
        scores = q @ k.transpose(0, 1, 3, 2) * scale  # (1, nh, s, s)
        mask = np.triu(np.ones((s, s), dtype=qkv.dtype), k=1) * -1e9
        scores = scores + mask.reshape(1, 1, s, s)
        weights = softmax(scores, axis=-1)
        out = weights @ v  # (1, nh, s, hd)
        # Update cache with current k/v.
        end = cache_len + s
        cache_k[:, cache_len:end, :] = k[0].transpose(1, 0, 2).reshape(nh, s, hd)
        cache_v[:, cache_len:end, :] = v[0].transpose(1, 0, 2).reshape(nh, s, hd)
        cache_len = end
    else:
        # Decode: append current k/v to cache and attend to all cached tokens.
        cache_k[:, cache_len, :] = k[0, :, 0, :]
        cache_v[:, cache_len, :] = v[0, :, 0, :]
        cache_len += 1
        k_all = cache_k[:, :cache_len, :].reshape(1, nh, cache_len, hd)
        v_all = cache_v[:, :cache_len, :].reshape(1, nh, cache_len, hd)
        scores = q @ k_all.transpose(0, 1, 3, 2) * scale  # (1, nh, 1, cache_len)
        weights = softmax(scores, axis=-1)
        out = weights @ v_all  # (1, nh, 1, hd)

    out = out.transpose(0, 2, 1, 3).reshape(b, s, nh * hd)
    kv_cache["cache_k"] = cache_k
    kv_cache["cache_v"] = cache_v
    kv_cache["cache_len"] = cache_len
    return out, kv_cache


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------
def sample_token(
    logits: np.ndarray,
    temperature: float = 1.0,
    top_k: int = 0,
    top_p: float = 1.0,
    rng: np.random.Generator | None = None,
) -> int:
    """Sample one token from logits."""
    if rng is None:
        rng = np.random.default_rng()
    logits = logits / max(temperature, 1e-6)
    if top_k > 0:
        kth = np.partition(logits, -top_k)[-top_k]
        logits = np.where(logits < kth, -1e9, logits)
    if top_p < 1.0:
        sorted_logits = np.sort(logits)[::-1]
        sorted_probs = softmax(sorted_logits)
        cumsum = np.cumsum(sorted_probs)
        cutoff = sorted_logits[np.argmax(cumsum > top_p)]
        logits = np.where(logits < cutoff, -1e9, logits)
    probs = softmax(logits)
    return int(rng.choice(len(probs), p=probs))
