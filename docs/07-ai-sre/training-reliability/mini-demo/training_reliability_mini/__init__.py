"""Training Reliability Mini — numpy-only models of large-scale training
fault tolerance (AI Infra Handbook, docs/07-ai-sre/training-reliability)."""
import sys as _sys

from .availability import (
    NODE_MTBF_LLAMA3_H,
    NODE_MTBF_RESEARCH_CLUSTER_H,
    availability,
    ettr_simple,
    expected_interruptions,
    job_mtbf_hours,
    scale_table,
    simulate_interruption_times,
)
from .checkpoint import (
    daly_optimal_interval_s,
    efficiency_curve,
    expected_lost_work_s,
    long_run_efficiency,
    optimal_interval_grid,
)
from .recovery import (
    TIMELINE_COLD_RESTART_MIN,
    FailureEvent,
    RecoveryResult,
    recover,
    sample_failures,
    simulate_run,
)
from .sdc import (
    deterministic_grad,
    dual_run_compare,
    hamming_distance,
    inject_bit_flips,
    locate_corrupted_shards,
    shard_fingerprints,
    spike_indices,
)
from .straggler import (
    detection_report,
    detect_stragglers,
    mitigate,
    outlier_scores,
    simulate_jittered_ranks,
    step_time_s,
)

# The function `availability` above shadows the submodule of the same name;
# rebind the package attribute so `from training_reliability_mini import
# availability` returns the module (matching the other submodules).
availability = _sys.modules[__name__ + ".availability"]

__all__ = [name for name in dir() if not name.startswith("_")]
__version__ = "0.1.0"
