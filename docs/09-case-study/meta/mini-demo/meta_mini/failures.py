"""Failure model: turning per-GPU rates into a synchronous-job hazard.

The central insight this module encodes: a synchronous training job of N GPUs
halts whenever *any one* GPU fails. So the per-step probability that the job is
interrupted is ``1 - (1 - p_gpu)^N`` — and ``N`` sits in the exponent. This is
why larger clusters are exponentially more fragile unless engineering drives the
single-GPU failure rate down.
"""

from __future__ import annotations


def per_step_cluster_hazard(
    rate_per_gpu_hour: float, n_gpus: int, step_seconds: float
) -> float:
    """Probability that the synchronous job is interrupted in a single step.

    Parameters
    ----------
    rate_per_gpu_hour:
        Failure rate of a single GPU, in faults per GPU per hour.
    n_gpus:
        Number of GPUs in the synchronous job.
    step_seconds:
        Wall-clock duration of one training step.

    Returns
    -------
    float
        ``1 - (1 - p_gpu)^n_gpus`` where ``p_gpu`` is the single-GPU
        per-step failure probability. For small ``p_gpu`` this is
        approximately ``n_gpus * p_gpu``.
    """
    if n_gpus <= 0:
        raise ValueError("n_gpus must be positive")
    if step_seconds <= 0:
        raise ValueError("step_seconds must be positive")
    if rate_per_gpu_hour < 0:
        raise ValueError("rate_per_gpu_hour must be non-negative")
    p_gpu = rate_per_gpu_hour * (step_seconds / 3600.0)
    # Any single GPU failing halts the whole synchronous job.
    return 1.0 - (1.0 - p_gpu) ** n_gpus
