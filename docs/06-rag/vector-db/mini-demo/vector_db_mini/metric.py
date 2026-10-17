"""Distance metrics for the vector_db_mini demo.

Convention: every metric returns a *distance* where smaller is better,
so that all indexes can treat metrics uniformly:

- l2      : squared-free L2 norm of the difference
- ip      : negative inner product (so that "closest" == "largest IP")
- cosine  : 1 - cos(theta); equals L2/2 on unit-normalized vectors
"""

from __future__ import annotations

import numpy as np

METRICS = ("l2", "ip", "cosine")


def _as_2d(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    return x


def normalize(vectors: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """L2-normalize each row; all-zero rows stay zero."""
    v = _as_2d(vectors)
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms = np.where(norms < eps, 1.0, norms)
    return v / norms


def l2_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise L2 distance between rows of a and rows of b -> (len(a), len(b))."""
    a = _as_2d(a)
    b = _as_2d(b)
    diff = a[:, None, :] - b[None, :, :]
    return np.linalg.norm(diff, axis=2)


def inner_product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise inner product between rows of a and rows of b -> (len(a), len(b))."""
    a = _as_2d(a)
    b = _as_2d(b)
    return a @ b.T


def cosine_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise cosine distance = 1 - cosine similarity."""
    an = normalize(a)
    bn = normalize(b)
    # clip against float noise so identical vectors give exactly 0
    sim = np.clip(an @ bn.T, -1.0, 1.0)
    return 1.0 - sim


def pairwise_distance(a: np.ndarray, b: np.ndarray, metric: str) -> np.ndarray:
    """Dispatch to the requested metric."""
    if metric == "l2":
        return l2_distance(a, b)
    if metric == "ip":
        return -inner_product(a, b)
    if metric == "cosine":
        return cosine_distance(a, b)
    raise ValueError(f"unknown metric: {metric!r}, expected one of {METRICS}")


def top_k(distances: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k smallest distances (ties broken by index, deterministic)."""
    d = np.asarray(distances)
    k = min(k, d.shape[0])
    # stable sort keeps tie order deterministic
    order = np.argsort(d, kind="stable")
    return order[:k]
