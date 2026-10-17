"""Silent Data Corruption (SDC) detection models.

SDC = hardware produces wrong results without any failure signal (no crash,
no error code). Defenses modeled here:

- dual-run comparison: run the same deterministic computation on two ranks
  and compare outputs bitwise (redundant computation);
- state hashing: fingerprint each rank's model/grad shard every step so a
  corrupted shard is pinned to a rank;
- loss/grad-norm spike check: a cheap statistical guard
  (ByteDance ByteRobust flags loss / grad-norm spikes at 5x).

First-hand anchors:
- Meta Llama 3 (arXiv:2407.21783) hit 6 SDC cases (1.4% of unexpected
  interruptions) in 54 days on 16K H100s.
- "Understanding Silent Data Corruptions in LLM Training" (ACL 2025,
  aclanthology 2025.acl-long.996) showed real unhealthy nodes can push
  training to different optima or cause loss spikes under deterministic XLA.
"""
from __future__ import annotations

import numpy as np


def deterministic_grad(rng_seed: int, dim: int = 4096) -> np.ndarray:
    """A reproducible pseudo-gradient vector (stands in for one rank's grad)."""
    if dim <= 0:
        raise ValueError("dim must be positive")
    rng = np.random.RandomState(rng_seed)
    return rng.standard_normal(dim).astype(np.float64)


def inject_bit_flips(vec: np.ndarray, n_flips: int, seed: int) -> np.ndarray:
    """Flip ``n_flips`` random bits in the float64 payload (SDC simulation)."""
    if n_flips < 0:
        raise ValueError("n_flips must be >= 0")
    corrupted = vec.copy()
    if n_flips == 0:
        return corrupted
    rng = np.random.RandomState(seed)
    view = corrupted.view(np.uint64)
    for _ in range(n_flips):
        idx = int(rng.randint(0, view.size))
        bit = int(rng.randint(0, 64))
        view[idx] ^= np.uint64(1 << bit)
    return corrupted


def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    """Total differing bits between two float64 arrays of equal shape."""
    if a.shape != b.shape:
        raise ValueError("shape mismatch")
    av = a.view(np.uint64)
    bv = b.view(np.uint64)
    return int(np.unpackbits(
        np.bitwise_xor(av, bv).view(np.uint8)).sum())


def dual_run_compare(rng_seed: int, dim: int = 4096, n_flips: int = 0,
                     inject_seed: int = 0) -> dict:
    """Two replicas compute the same deterministic gradient; compare bitwise."""
    a = deterministic_grad(rng_seed, dim)
    b = inject_bit_flips(a, n_flips, inject_seed) if n_flips else a.copy()
    dist = hamming_distance(a, b)
    return {"mismatch": dist > 0, "bits_differing": dist}


def shard_fingerprints(shards: np.ndarray) -> np.ndarray:
    """Cheap per-shard fingerprint (sum + checksum), one row per rank.

    ``shards`` is (n_ranks, dim). Used to pin a corrupted replica to a rank
    by comparing fingerprints of two checkpoints / replicas.
    """
    if shards.ndim != 2:
        raise ValueError("shards must be 2-D (n_ranks, dim)")
    sums = shards.sum(axis=1)
    int_view = np.abs(shards).view(np.uint64).astype(np.uint64)
    checksums = (int_view % np.uint64(1000003)).sum(axis=1) % np.uint64(2**31)
    return np.stack([sums, checksums.astype(np.float64)], axis=1)


def locate_corrupted_shards(replica_a: np.ndarray, replica_b: np.ndarray) -> np.ndarray:
    """Indices of all ranks whose two replicas disagree; empty if all agree."""
    if replica_a.shape != replica_b.shape or replica_a.ndim != 2:
        raise ValueError("replicas must be (n_ranks, dim) with equal shapes")
    fa = shard_fingerprints(replica_a)
    fb = shard_fingerprints(replica_b)
    return np.nonzero(np.any(fa != fb, axis=1))[0]


def spike_indices(losses: np.ndarray, factor: float = 5.0,
                  window: int = 20) -> np.ndarray:
    """Indices where loss exceeds ``factor`` x rolling median (SDC symptom).

    Mirrors the production heuristic family (ByteRobust flags 5x loss /
    grad-norm spikes). Uses a trailing median of the previous ``window``
    steps so a genuinely diverging run is not flagged forever.
    """
    if losses.ndim != 1 or losses.size < 2:
        raise ValueError("losses must be a 1-D array with >= 2 entries")
    if factor <= 1.0:
        raise ValueError("factor must be > 1")
    flagged = []
    for i in range(1, losses.size):
        base = np.median(losses[max(0, i - window):i])
        if base > 0 and losses[i] > factor * base:
            flagged.append(i)
    return np.asarray(flagged, dtype=int)
