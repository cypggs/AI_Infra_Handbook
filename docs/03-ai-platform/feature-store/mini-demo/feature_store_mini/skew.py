"""Training/serving skew detection.

Skew appears when the *same logical feature* is computed by two
different code paths (an offline batch pipeline for training and an
online/streaming pipeline for serving) and the results disagree.
This module provides the small toolkit used to measure it:
paired-sample comparison, distribution summaries and PSI.
"""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def feature_distribution(values: Iterable[float]) -> dict:
    """Basic statistics of a numeric feature sample."""
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("values must not be empty")
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def psi(expected: Iterable[float], actual: Iterable[float], bins: int = 10) -> float:
    """Population Stability Index between two samples.

    Values outside the expected range are clamped into the edge bins.
    PSI < 0.1  : no significant drift
    PSI 0.1-0.25: moderate drift
    PSI > 0.25 : significant drift
    """
    e = np.asarray(list(expected), dtype=float)
    a = np.asarray(list(actual), dtype=float)
    if e.size == 0 or a.size == 0:
        raise ValueError("samples must not be empty")
    lo = float(min(e.min(), a.min()))
    hi = float(max(e.max(), a.max()))
    edges = np.linspace(lo, hi, bins + 1)
    if hi == lo:  # degenerate constant feature: single bin
        edges = np.array([lo, lo + 1.0])
    e_counts, _ = np.histogram(e, bins=edges)
    a_counts, _ = np.histogram(a, bins=edges)
    e_pct = np.clip(e_counts / max(e_counts.sum(), 1), 1e-6, None)
    a_pct = np.clip(a_counts / max(a_counts.sum(), 1), 1e-6, None)
    return float(((e_pct - a_pct) * np.log(e_pct / a_pct)).sum())


def detect_skew(
    sample_pairs: Iterable[tuple[float, float]],
    abs_tol: float = 0.0,
    rel_tol: float = 1e-6,
) -> dict:
    """Compare paired (offline, online) values of one logical feature.

    A pair is *mismatched* when the absolute difference exceeds
    ``abs_tol + rel_tol * abs(offline_value)`` — the same rule as
    ``math.isclose``.
    """
    pairs = [(float(o), float(s)) for o, s in sample_pairs]
    if not pairs:
        raise ValueError("sample_pairs must not be empty")
    mismatched = []
    max_abs_diff = 0.0
    max_rel_diff = 0.0
    for offline_val, serving_val in pairs:
        diff = abs(offline_val - serving_val)
        max_abs_diff = max(max_abs_diff, diff)
        if offline_val != 0.0:
            max_rel_diff = max(max_rel_diff, diff / abs(offline_val))
        if not math.isclose(offline_val, serving_val, abs_tol=abs_tol, rel_tol=rel_tol):
            mismatched.append((offline_val, serving_val))
    return {
        "compared": len(pairs),
        "mismatched": len(mismatched),
        "max_abs_diff": max_abs_diff,
        "max_rel_diff": max_rel_diff,
        "skewed": bool(mismatched),
        "examples": mismatched[:5],
    }
