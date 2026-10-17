"""Checkpoint interval optimization models.

Models the classic checkpoint/restart trade-off:

- full checkpoint blocks training for ``ckpt_s`` seconds every ``T`` steps;
- a failure loses the work since the last checkpoint (expected T/2 steps)
  plus a fixed restart cost;
- the long-run efficiency is maximized at an optimal interval.

Includes the Daly approximation T* = sqrt(2 * C * M) and an exact grid
search over the long-run efficiency, plus incremental checkpoints that
reduce the per-checkpoint cost by a ``delta`` ratio.
"""
from __future__ import annotations

import numpy as np


def daly_optimal_interval_s(ckpt_s: float, mtbf_h: float) -> float:
    """Daly's approximation of the optimal checkpoint interval (seconds).

    T* ~= sqrt(2 * C * M), where C is the checkpoint cost and M the MTBF
    (both in the same time unit).
    """
    if ckpt_s <= 0:
        raise ValueError("ckpt_s must be positive")
    if mtbf_h <= 0:
        raise ValueError("mtbf_h must be positive")
    return float(np.sqrt(2.0 * ckpt_s * mtbf_h * 3600.0))


def expected_lost_work_s(interval_steps: int, step_s: float, restart_s: float) -> float:
    """Expected work lost per failure: half an interval + restart time."""
    if interval_steps <= 0:
        raise ValueError("interval_steps must be positive")
    if step_s <= 0 or restart_s < 0:
        raise ValueError("bad step_s / restart_s")
    return interval_steps * step_s / 2.0 + restart_s


def long_run_efficiency(interval_steps: int, step_s: float, ckpt_s: float,
                        mtbf_h: float, restart_s: float) -> float:
    """Long-run useful-work efficiency of periodic checkpointing.

    One failure cycle spans on average ``mtbf_h`` of wall-clock work; within a
    cycle the job pays (intervals taken) * ckpt_s of blocking time and loses
    expected_lost_work_s when the failure strikes.
    """
    if interval_steps <= 0:
        raise ValueError("interval_steps must be positive")
    if step_s <= 0 or ckpt_s < 0 or mtbf_h <= 0 or restart_s < 0:
        raise ValueError("bad parameters")
    cycle_work_s = mtbf_h * 3600.0
    steps_per_cycle = cycle_work_s / step_s
    n_checkpoints = steps_per_cycle / interval_steps
    lost_s = expected_lost_work_s(interval_steps, step_s, restart_s)
    total = cycle_work_s + n_checkpoints * ckpt_s + lost_s
    return cycle_work_s / total


def optimal_interval_grid(step_s: float, ckpt_s: float, mtbf_h: float,
                          restart_s: float, max_steps: int = 5000) -> dict:
    """Exact optimum of long_run_efficiency over interval steps 1..max_steps."""
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    grid = np.arange(1, max_steps + 1)
    eff = np.array([long_run_efficiency(int(t), step_s, ckpt_s, mtbf_h, restart_s)
                    for t in grid])
    i = int(np.argmax(eff))
    return {"interval_steps": int(grid[i]), "efficiency": float(eff[i]),
            "daly_steps": daly_optimal_interval_s(ckpt_s, mtbf_h) / step_s}


def efficiency_curve(step_s: float, ckpt_s: float, mtbf_h: float,
                     restart_s: float, max_steps: int = 5000,
                     every: int = 25) -> list[dict]:
    """Sampled efficiency curve for reporting (interval vs efficiency)."""
    rows = []
    for t in range(every, max_steps + 1, every):
        rows.append({"interval_steps": t,
                     "efficiency": long_run_efficiency(t, step_s, ckpt_s, mtbf_h, restart_s)})
    return rows
