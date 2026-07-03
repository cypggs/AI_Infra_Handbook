"""SDC detector: periodic validation that catches silent corruption.

Silent Data Corruption (SDC) does not halt the job — it silently corrupts
state (e.g. NaN propagation or, worse, corrupted gradient variance that stays
within numeric bounds). The only way to catch it is to periodically validate
training state against a reference.

Meta deploys three detection mechanisms with different latencies:
  * Fleetscanner — directed micro-benchmarks during maintenance; 45-60 day
    fleet sweep.
  * Ripple — ms-to-second tests co-located with workloads; days-scale sweep.
  * Hardware Sentinel — kernel-space, continuous, +41% over testing-based.

In this simulator we collapse them into a single tunable ``validation_interval``
(the detection latency) plus ``validation_seconds`` (the validation cost). The
key correctness property the simulator relies on: *validation runs before
checkpoint on the same step*, so as long as ``validation_interval <=
ckpt_interval`` an SDC is always caught before it can be baked into a
checkpoint.
"""

from __future__ import annotations


def is_validation_step(step: int, validation_interval: int) -> bool:
    """True if SDC validation runs at the end of ``step``.

    ``validation_interval == 0`` disables validation entirely (used to model the
    "naive" configuration with no detector).
    """
    if validation_interval < 0:
        raise ValueError("validation_interval must be >= 0")
    if validation_interval == 0:
        return False
    return step % validation_interval == 0
