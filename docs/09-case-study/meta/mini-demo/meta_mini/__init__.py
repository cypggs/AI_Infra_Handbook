"""Meta mini demo package.

A deterministic, CPU-only simulator for the failure economics of large-scale
synchronous training — faithful to Meta's public reliability numbers
(>66% interruptions from hardware, SDC ~1/1000 devices, >95% effective
training time, ~50x interruption-rate reduction).
"""

from meta_mini.model import JobConfig, SimResult
from meta_mini.failures import per_step_cluster_hazard
from meta_mini.simulator import TrainingSimulator
from meta_mini.metrics import (
    effective_utilization,
    recompute_overhead_pct,
    checkpoint_overhead_pct,
    restart_overhead_pct,
    validation_overhead_pct,
)

__all__ = [
    "JobConfig",
    "SimResult",
    "per_step_cluster_hazard",
    "TrainingSimulator",
    "effective_utilization",
    "recompute_overhead_pct",
    "checkpoint_overhead_pct",
    "restart_overhead_pct",
    "validation_overhead_pct",
]
