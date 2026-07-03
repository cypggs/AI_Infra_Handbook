"""Checkpoint manager: fixed-interval synchronous checkpoints.

In the simulator the checkpoint policy is encoded directly in ``JobConfig``
(``ckpt_interval`` / ``ckpt_seconds``). This module exists to (a) document the
semantics and (b) provide the small helper that decides whether a given step is
a checkpoint boundary. Keeping it as its own module mirrors how Meta factors
checkpoint logic out of the training loop.
"""

from __future__ import annotations


def is_checkpoint_step(step: int, ckpt_interval: int) -> bool:
    """True if a synchronous checkpoint is written at the end of ``step``.

    Checkpoints are taken at step boundaries that are multiples of
    ``ckpt_interval`` (steps are 1-indexed: the first completed step is 1).
    """
    if ckpt_interval < 1:
        raise ValueError("ckpt_interval must be >= 1")
    return step % ckpt_interval == 0
