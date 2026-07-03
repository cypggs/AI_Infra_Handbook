"""Data structures for the training reliability simulator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobConfig:
    """Configuration for a synchronous training job simulation.

    All failure rates are expressed as *per GPU per hour*; the simulator
    converts them to a per-step cluster hazard (see ``failures.py``), which is
    what actually matters for a synchronous job — any single GPU failing halts
    the whole job.
    """

    # --- cluster & workload ---
    n_gpus: int = 16384
    target_steps: int = 10000
    step_seconds: float = 5.0

    # --- failure rates (per GPU per hour) ---
    # static / transient hardware faults (HBM, SRAM, switch, ...) -> immediate halt
    hard_fail_rate: float = 8.0e-5
    # silent data corruption rate (silicon defects; ~1/1000 devices at Meta scale)
    sdc_rate: float = 6.0e-5

    # --- checkpoint policy ---
    ckpt_interval: int = 200          # checkpoint every N steps
    ckpt_seconds: float = 30.0        # write duration (Tectonic-backed, fast)

    # --- recovery policy ---
    restart_seconds: float = 120.0    # process-group rebuild + auto-restart

    # --- SDC detection policy ---
    # validation every N steps (0 disables validation entirely).
    # Maps to the detection latency of Fleetscanner / Ripple / Hardware Sentinel.
    validation_interval: int = 100
    validation_seconds: float = 15.0

    # --- determinism ---
    seed: int = 0

    # safety cap on total step executions to guarantee termination
    max_step_budget: int = 5_000_000

    def __post_init__(self) -> None:
        if self.n_gpus <= 0:
            raise ValueError("n_gpus must be positive")
        if self.target_steps <= 0:
            raise ValueError("target_steps must be positive")
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be positive")
        if self.ckpt_interval < 1:
            raise ValueError("ckpt_interval must be >= 1")
        if self.validation_interval < 0:
            raise ValueError("validation_interval must be >= 0")


@dataclass(frozen=True)
class SimResult:
    """Outcome of one simulated run."""

    completed: bool
    target: int                 # durable forward steps the job needed
    recompute_steps: int        # steps executed but later discarded by rollback
    ckpt_seconds: float         # wall time spent writing checkpoints
    restart_seconds: float      # wall time spent rebuilding process groups
    validation_seconds: float   # wall time spent on SDC validation
    interruptions: int          # count of hard-failure halts
    sdc_detected: int           # SDCs caught by validation before being baked in
    sdc_baked: int              # SDCs that corrupted a checkpoint or reached target
    step_seconds: float
    wall_seconds: float         # total wall-clock time
