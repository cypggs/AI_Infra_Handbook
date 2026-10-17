"""Failure injection, taxonomy and elastic recovery workflow simulation.

The recovery timeline constants come from first-hand measurements:

- TrainMover (arXiv:2412.12636, Meta), Table 1, 8,192-GPU production restart:
  total 6.47 min = stop/cleanup 0.52 + reschedule 1.50 + init 4.45,
  where init = checkpoint load 1.56 + NCCL init 1.09 + cold warmup 1.80.
- ByteDance ByteRobust (arXiv:2509.16293): runtime detection latency
  ~2 s OS kernel / ~10 s GPU / ~30 s NIC; hot-update restart 11.04x faster
  than full requeue (46-65 s vs 454-768 s).
- Llama 3 (arXiv:2407.21783): 466 interruptions in 54 days; ~78% of the
  419 unexpected ones are hardware; GPU is the largest category (58.7%).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# TrainMover Table 1 breakdown, minutes (8,192-GPU job restart).
TIMELINE_STOP_MIN = 0.52
TIMELINE_RESCHEDULE_MIN = 1.50
TIMELINE_CKPT_LOAD_MIN = 1.56
TIMELINE_NCCL_MIN = 1.09
TIMELINE_WARMUP_MIN = 1.80
TIMELINE_COLD_RESTART_MIN = (
    TIMELINE_STOP_MIN + TIMELINE_RESCHEDULE_MIN
    + TIMELINE_CKPT_LOAD_MIN + TIMELINE_NCCL_MIN + TIMELINE_WARMUP_MIN
)

# ByteDust ByteRobust detection latencies, seconds.
DETECT_OS_KERNEL_S = 2.0
DETECT_GPU_S = 10.0
DETECT_NIC_S = 30.0

# ByteRobust hot-update restart, seconds (46-65 s measured range midpoint).
HOT_UPDATE_RESTART_S = 55.0

# Llama 3 unexpected-interruption taxonomy (share of the 419 unexpected).
TAXONOMY_GPU = 0.587
TAXONOMY_NETWORK = 0.084
TAXONOMY_HOST = 0.10
TAXONOMY_SOFTWARE = 0.145
TAXONOMY_OTHER = 1.0 - (TAXONOMY_GPU + TAXONOMY_NETWORK + TAXONOMY_HOST + TAXONOMY_SOFTWARE)

# Detection latency (seconds) and restart path per category in this simulation.
CATEGORY_PROFILE = {
    "gpu": {"detect_s": DETECT_GPU_S, "standby_ok": True},
    "network": {"detect_s": DETECT_NIC_S, "standby_ok": True},
    "host": {"detect_s": DETECT_OS_KERNEL_S, "standby_ok": True},
    "software": {"detect_s": DETECT_OS_KERNEL_S, "standby_ok": False},
    "other": {"detect_s": DETECT_OS_KERNEL_S, "standby_ok": False},
}


@dataclass
class FailureEvent:
    """A single injected failure."""
    time_h: float
    category: str
    node: int


@dataclass
class RecoveryResult:
    """Outcome of recovering from one failure."""
    strategy: str
    detect_s: float
    restart_s: float
    rollback_steps: int
    lost_s: float          # rollback waste + detection + restart
    downtime_s: float      # detection + restart (job paused)


def sample_failures(duration_h: float, n_nodes: int, node_mtbf_h: float,
                    seed: int) -> list[FailureEvent]:
    """Deterministic failure trace with Llama 3 taxonomy shares."""
    from .availability import simulate_interruption_times

    times = simulate_interruption_times(duration_h, n_nodes, node_mtbf_h, seed)
    rng = np.random.RandomState(seed + 1)
    categories = list(CATEGORY_PROFILE.keys())
    weights = [TAXONOMY_GPU, TAXONOMY_NETWORK, TAXONOMY_HOST,
               TAXONOMY_SOFTWARE, TAXONOMY_OTHER]
    cats = rng.choice(categories, size=len(times), p=weights)
    nodes = rng.randint(0, n_nodes, size=len(times))
    return [FailureEvent(float(t), str(c), int(n))
            for t, c, n in zip(times, cats, nodes)]


def recover(event: FailureEvent, strategy: str, interval_steps: int,
            step_s: float) -> RecoveryResult:
    """Recovery outcome for one failure under a strategy.

    ``strategy`` is "cold" (full requeue, TrainMover timeline) or
    "hot" (warm standby + hot-update, ByteRobust timeline; software/other
    faults still need a full restart).
    """
    if interval_steps <= 0 or step_s <= 0:
        raise ValueError("bad interval_steps / step_s")
    profile = CATEGORY_PROFILE[event.category]
    detect_s = profile["detect_s"]
    rollback_s = interval_steps * step_s / 2.0
    if strategy == "cold":
        restart_s = TIMELINE_COLD_RESTART_MIN * 60.0
    elif strategy == "hot":
        restart_s = HOT_UPDATE_RESTART_S if profile["standby_ok"] \
            else TIMELINE_COLD_RESTART_MIN * 60.0
    else:
        raise ValueError(f"unknown strategy: {strategy}")
    downtime_s = detect_s + restart_s
    lost_s = rollback_s + downtime_s
    return RecoveryResult(strategy, detect_s, restart_s,
                          interval_steps // 2, lost_s, downtime_s)


def simulate_run(duration_h: float, n_nodes: int, node_mtbf_h: float,
                 step_s: float, interval_steps: int, strategy: str,
                 seed: int) -> dict:
    """Simulate one training run and compute ETTR (no checkpoint overhead).

    Returns interruption count, total lost seconds, ETTR and per-category
    breakdown. Deterministic for a fixed seed.
    """
    if duration_h <= 0 or step_s <= 0:
        raise ValueError("bad duration_h / step_s")
    events = sample_failures(duration_h, n_nodes, node_mtbf_h, seed)
    total_s = duration_h * 3600.0
    lost_s = 0.0
    per_category: dict[str, int] = {}
    for ev in events:
        res = recover(ev, strategy, interval_steps, step_s)
        lost_s += res.lost_s
        per_category[ev.category] = per_category.get(ev.category, 0) + 1
    productive_s = max(total_s - lost_s, 0.0)
    return {
        "interruptions": len(events),
        "lost_h": lost_s / 3600.0,
        "ettr": productive_s / total_s,
        "per_category": per_category,
    }
