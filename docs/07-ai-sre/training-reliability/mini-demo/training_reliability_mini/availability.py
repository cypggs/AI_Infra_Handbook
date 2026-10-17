"""Training Reliability Mini: availability and MTBF/MTTR math models.

Pure numpy models for reasoning about large-scale training reliability:

- per-node MTBF -> job-level MTBF under independent failures
- availability vs cluster scale for different repair (MTTR) strategies
- calibration presets from published first-hand measurements
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Calibration presets (first-hand sources, see docs/07-ai-sre/training-reliability)
# ---------------------------------------------------------------------------
# Kokolis et al., HPCA 2025 ("Revisiting Reliability in Large-Scale ML Research
# Clusters", Meta): MTTF of a 1,024-GPU job is 7.9 hours.
#   -> implied per-node MTBF = 7.9 h * 1024 = 8089.6 h ~= 337 days
NODE_MTBF_RESEARCH_CLUSTER_H = 7.9 * 1024.0

# Meta Llama 3 (arXiv:2407.21783): 466 interruptions over 54 days on 16,384
# H100 GPUs -> one interruption every 54*24/466 = 2.78 h.
#   -> implied per-node MTBF = 2.78 h * 16384 = 45562 h ~= 5.05 years
LLAMA3_INTERRUPTION_INTERVAL_H = 54.0 * 24.0 / 466.0
NODE_MTBF_LLAMA3_H = LLAMA3_INTERRUPTION_INTERVAL_H * 16384.0


def job_mtbf_hours(n_nodes: int, node_mtbf_hours: float) -> float:
    """Job-level MTBF assuming independent node failures (exponential model).

    With N independent nodes each failing with rate 1/m, the job fails with
    rate N/m, so job MTBF = m / N.
    """
    if n_nodes <= 0:
        raise ValueError("n_nodes must be positive")
    if node_mtbf_hours <= 0:
        raise ValueError("node_mtbf_hours must be positive")
    return node_mtbf_hours / float(n_nodes)


def expected_interruptions(duration_hours: float, n_nodes: int, node_mtbf_hours: float) -> float:
    """Expected number of job interruptions over a run of ``duration_hours``."""
    if duration_hours < 0:
        raise ValueError("duration_hours must be >= 0")
    return duration_hours / job_mtbf_hours(n_nodes, node_mtbf_hours)


def availability(mtbf_hours: float, mttr_hours: float) -> float:
    """Steady-state availability A = MTBF / (MTBF + MTTR)."""
    if mtbf_hours <= 0:
        raise ValueError("mtbf_hours must be positive")
    if mttr_hours < 0:
        raise ValueError("mttr_hours must be >= 0")
    return mtbf_hours / (mtbf_hours + mttr_hours)


def ettr_simple(mtbf_hours: float, mttr_hours: float, rollback_hours: float = 0.0) -> float:
    """Simplified Effective Training Time Ratio.

    Between two failures the job loses ``rollback_hours`` of useful work
    (checkpoint rollback, wasted steps) in addition to the ``mttr_hours``
    spent detecting / recovering. ETTR = productive time / wall time.
    """
    if rollback_hours < 0:
        raise ValueError("rollback_hours must be >= 0")
    cycle = mtbf_hours + mttr_hours + rollback_hours
    return mtbf_hours / cycle


def scale_table(node_mtbf_hours: float,
                scales=(128, 1024, 8192, 16384, 32768, 131072),
                mttr_cold_h: float = 1.0,
                mttr_hot_h: float = 5.0 / 60.0) -> list[dict]:
    """Availability of a synchronous training job at several scales.

    ``mttr_cold_h`` models repair-and-requeue (~60 min), ``mttr_hot_h``
    models warm-standby swap (~5 min).
    """
    rows = []
    for n in scales:
        mtbf = job_mtbf_hours(n, node_mtbf_hours)
        rows.append({
            "nodes": n,
            "job_mtbf_h": mtbf,
            "avail_cold": availability(mtbf, mttr_cold_h),
            "avail_hot": availability(mtbf, mttr_hot_h),
        })
    return rows


def simulate_interruption_times(duration_h: float, n_nodes: int,
                                node_mtbf_h: float, seed: int) -> np.ndarray:
    """Deterministic Poisson failure-process sample.

    Returns sorted interruption wall-clock times (hours) within [0, duration].
    Uses a fixed-seed RandomState so tests and the demo are reproducible.
    """
    if duration_h <= 0:
        raise ValueError("duration_h must be positive")
    rng = np.random.RandomState(seed)
    lam = expected_interruptions(duration_h, n_nodes, node_mtbf_h)
    # Sample the count, then uniform order statistics (Poisson process).
    count = rng.poisson(lam)
    times = np.sort(rng.uniform(0.0, duration_h, size=count))
    return times
