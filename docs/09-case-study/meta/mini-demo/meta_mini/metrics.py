"""Metrics derived from a ``SimResult``.

All percentages are fractions of total wall-clock time. They partition the wall
clock:

    effective + recompute + checkpoint + restart + validation == 1

where ``effective`` is the share spent on *durable forward progress* (the
target steps). This is the same yardstick Meta reports as "effective training
time" (>95% for Llama 3).
"""

from __future__ import annotations

from meta_mini.model import SimResult


def effective_utilization(r: SimResult) -> float:
    """Share of wall clock spent on durable forward progress (the >95% metric)."""
    if r.wall_seconds <= 0:
        return 0.0
    return (r.target * r.step_seconds) / r.wall_seconds


def recompute_overhead_pct(r: SimResult) -> float:
    """Share of wall clock wasted re-running steps discarded by rollback."""
    if r.wall_seconds <= 0:
        return 0.0
    return (r.recompute_steps * r.step_seconds) / r.wall_seconds


def checkpoint_overhead_pct(r: SimResult) -> float:
    """Share of wall clock spent writing checkpoints."""
    if r.wall_seconds <= 0:
        return 0.0
    return r.ckpt_seconds / r.wall_seconds


def restart_overhead_pct(r: SimResult) -> float:
    """Share of wall clock spent rebuilding process groups after a halt."""
    if r.wall_seconds <= 0:
        return 0.0
    return r.restart_seconds / r.wall_seconds


def validation_overhead_pct(r: SimResult) -> float:
    """Share of wall clock spent on SDC validation."""
    if r.wall_seconds <= 0:
        return 0.0
    return r.validation_seconds / r.wall_seconds
