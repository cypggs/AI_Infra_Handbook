"""Vector quantization for the vector_db_mini demo.

Two classic schemes, implemented deterministically (fixed-seed k-means):

- ScalarQuantizer (SQ): per-dimension min/max linear mapping to integers.
- ProductQuantizer (PQ): split the vector into m sub-vectors, run k-means
  with k centroids per sub-space, store only the centroid ids.

Both expose encode()/decode(); PQ additionally exposes adc_distances()
(asymmetric distance computation) which is what real PQ indexes use at
query time: the query stays float, only the database vectors are codes.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def _kmeans(
    points: np.ndarray,
    k: int,
    iters: int = 20,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Minimal deterministic k-means.

    Returns (centroids (k, d), assignments (n,)). Initialization uses
    evenly spaced samples + a seeded RandomState so repeated runs agree.
    """
    points = np.asarray(points, dtype=np.float64)
    n, d = points.shape
    k = max(1, min(k, n))
    rng = np.random.RandomState(seed)
    step = max(1, n // k)
    init_idx = (np.arange(k) * step + rng.randint(0, step)) % n
    centroids = points[init_idx].copy()

    assignments = np.zeros(n, dtype=np.int64)
    for _ in range(iters):
        # assign
        dists = np.linalg.norm(
            points[:, None, :] - centroids[None, :, :], axis=2
        )
        new_assign = np.argmin(dists, axis=1)
        # update
        new_centroids = centroids.copy()
        for c in range(k):
            members = points[new_assign == c]
            if len(members):
                new_centroids[c] = members.mean(axis=0)
        shift = np.max(np.linalg.norm(new_centroids - centroids, axis=1))
        centroids, assignments = new_centroids, new_assign
        if shift < 1e-9:
            break
    return centroids, assignments


class ScalarQuantizer:
    """Per-dimension uniform quantization over [min, max]."""

    def __init__(self, bits: int = 8) -> None:
        if not (1 <= bits <= 16):
            raise ValueError("bits must be in [1, 16]")
        self.bits = bits
        self._mins: Optional[np.ndarray] = None
        self._maxs: Optional[np.ndarray] = None

    def fit(self, vectors: np.ndarray) -> "ScalarQuantizer":
        v = np.asarray(vectors, dtype=np.float64)
        self._mins = v.min(axis=0)
        self._maxs = v.max(axis=0)
        # avoid zero-width ranges (e.g. a constant dimension)
        self._maxs = np.where(self._maxs > self._mins, self._maxs, self._mins + 1.0)
        return self

    @property
    def levels(self) -> int:
        return (1 << self.bits) - 1

    def encode(self, vectors: np.ndarray) -> np.ndarray:
        if self._mins is None:
            raise RuntimeError("call fit() before encode()")
        v = np.asarray(vectors, dtype=np.float64)
        scaled = (v - self._mins) / (self._maxs - self._mins) * self.levels
        return np.clip(np.round(scaled), 0, self.levels).astype(np.uint32)

    def decode(self, codes: np.ndarray) -> np.ndarray:
        if self._mins is None:
            raise RuntimeError("call fit() before decode()")
        c = np.asarray(codes, dtype=np.float64)
        return self._mins + (self._maxs - self._mins) * (c / self.levels)

    def compression_ratio(self, dim: int) -> float:
        """compressed bytes per vector / original float64 bytes per vector."""
        return self.bits / 64.0


class ProductQuantizer:
    """Classic PQ: m sub-spaces, k centroids each, seeded k-means training."""

    def __init__(
        self,
        m: int = 4,
        k: int = 16,
        iters: int = 20,
        seed: int = 0,
    ) -> None:
        if m < 1:
            raise ValueError("m must be >= 1")
        if k < 2:
            raise ValueError("k must be >= 2")
        self.m = m
        self.k = k
        self.iters = iters
        self.seed = seed
        self.dim_: Optional[int] = None
        self.codebooks: Optional[np.ndarray] = None  # (m, k, sub_dim)

    def fit(self, vectors: np.ndarray) -> "ProductQuantizer":
        v = np.asarray(vectors, dtype=np.float64)
        n, dim = v.shape
        if dim % self.m != 0:
            raise ValueError(f"dim {dim} must be divisible by m {self.m}")
        self.dim_ = dim
        sub_dim = dim // self.m
        books = np.zeros((self.m, self.k, sub_dim))
        for i in range(self.m):
            sub = v[:, i * sub_dim : (i + 1) * sub_dim]
            centroids, _ = _kmeans(sub, self.k, iters=self.iters, seed=self.seed + i)
            books[i] = centroids
        self.codebooks = books
        return self

    def encode(self, vectors: np.ndarray) -> np.ndarray:
        if self.codebooks is None:
            raise RuntimeError("call fit() before encode()")
        v = np.asarray(vectors, dtype=np.float64)
        sub_dim = self.dim_ // self.m
        codes = np.zeros((len(v), self.m), dtype=np.int64)
        for i in range(self.m):
            sub = v[:, i * sub_dim : (i + 1) * sub_dim]
            dists = np.linalg.norm(
                sub[:, None, :] - self.codebooks[i][None, :, :], axis=2
            )
            codes[:, i] = np.argmin(dists, axis=1)
        return codes

    def decode(self, codes: np.ndarray) -> np.ndarray:
        if self.codebooks is None:
            raise RuntimeError("call fit() before decode()")
        c = np.asarray(codes)
        sub_dim = self.dim_ // self.m
        out = np.zeros((len(c), self.dim_))
        for i in range(self.m):
            out[:, i * sub_dim : (i + 1) * sub_dim] = self.codebooks[i][c[:, i]]
        return out

    def adc_distances(self, query: np.ndarray, codes: np.ndarray) -> np.ndarray:
        """Asymmetric distance: float query vs encoded vectors.

        Build a per-subspace lookup table of query-to-centroid distances,
        then sum the looked-up distances per code. This is exactly what
        FAISS IVF-PQ does at query time.
        """
        if self.codebooks is None:
            raise RuntimeError("call fit() first")
        q = np.asarray(query, dtype=np.float64).reshape(-1)
        c = np.asarray(codes)
        sub_dim = self.dim_ // self.m
        lut = np.zeros((self.m, self.k))
        for i in range(self.m):
            sub_q = q[i * sub_dim : (i + 1) * sub_dim]
            # squared L2: sums across sub-spaces then equal ||recon - q||^2
            lut[i] = np.sum((self.codebooks[i] - sub_q) ** 2, axis=1)
        return lut[np.arange(self.m)[None, :], c].sum(axis=1)

    def compression_ratio(self) -> float:
        """bits per vector / 64 bits per original float64 dimension."""
        bits_per_vector = self.m * int(np.ceil(np.log2(self.k)))
        return bits_per_vector / (64.0 * self.dim_) if self.dim_ else 1.0
