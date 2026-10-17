"""Straggler (fail-slow) detection and mitigation models.

In synchronous data/pipeline parallel training one step takes as long as the
slowest participating rank, so a single degraded node inflates every step.
This module models:

- step time = max(rank times) under synchronous execution;
- median-based outlier detection on per-rank step times;
- mitigation by evicting/replacing flagged ranks (whole PP-group eviction in
  production, e.g. ByteDance ByteRobust over-evicts 8 machines to catch 1-2).

First-hand anchors: Alibaba FALCON (arXiv:2410.12588) found stragglers
"common but largely unheeded" on a >10,000-GPU cluster, lasting "tens of
seconds to nearly ten hours" with 1.34% average JCT impact, detected with
>99% accuracy and mitigating 60.1% of the slowdown when deployed.
"""
from __future__ import annotations

import numpy as np


def step_time_s(rank_times_s: np.ndarray) -> float:
    """Synchronous step time: the slowest rank dominates."""
    if rank_times_s.size == 0:
        raise ValueError("rank_times_s must be non-empty")
    return float(np.max(rank_times_s))


def outlier_scores(rank_times_s: np.ndarray) -> np.ndarray:
    """Per-rank slowness score: time / median(time) - 1 (0 == median speed)."""
    if rank_times_s.size == 0:
        raise ValueError("rank_times_s must be non-empty")
    median = np.median(rank_times_s)
    if median <= 0:
        raise ValueError("median rank time must be positive")
    return rank_times_s / median - 1.0


def detect_stragglers(rank_times_s: np.ndarray, threshold: float = 0.15) -> np.ndarray:
    """Flag ranks slower than ``threshold`` (fraction) above the median."""
    scores = outlier_scores(rank_times_s)
    return np.nonzero(scores > threshold)[0]


def mitigate(rank_times_s: np.ndarray, flagged: np.ndarray,
             replacement_time_s: float | None = None) -> np.ndarray:
    """Replace flagged ranks (evict + standby swap) and return new rank times.

    ``replacement_time_s=None`` evicts without replacement (world shrinks).
    """
    if flagged.size == 0:
        return rank_times_s.copy()
    keep = np.setdiff1d(np.arange(rank_times_s.size), flagged)
    remaining = rank_times_s[keep]
    if replacement_time_s is None:
        return remaining
    if replacement_time_s <= 0:
        raise ValueError("replacement_time_s must be positive")
    return np.append(remaining, np.full(flagged.size, replacement_time_s))


def detection_report(true_slow: set[int], flagged: set[int]) -> dict:
    """Precision/recall/F1 of a detection pass (deterministic)."""
    tp = len(true_slow & flagged)
    fp = len(flagged - true_slow)
    fn = len(true_slow - flagged)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"precision": precision, "recall": recall, "f1": f1}


def simulate_jittered_ranks(n_ranks: int, step_s: float, sigma_s: float,
                            seed: int, slow_ranks: dict[int, float] | None = None) -> np.ndarray:
    """Deterministic per-rank times: lognormal jitter + optional slow ranks.

    ``slow_ranks`` maps rank -> slowdown factor (1.2 means 20% slower).
    """
    if n_ranks <= 0 or step_s <= 0 or sigma_s < 0:
        raise ValueError("bad parameters")
    rng = np.random.RandomState(seed)
    times = step_s * np.exp(rng.normal(0.0, sigma_s / step_s, size=n_ranks))
    for rank, factor in (slow_ranks or {}).items():
        if not 0 <= rank < n_ranks:
            raise ValueError("slow rank index out of range")
        times[rank] = step_s * factor
    return times
