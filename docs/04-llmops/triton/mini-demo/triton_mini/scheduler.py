"""Scheduler implementations for the Mini Triton demo."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

from .config_parser import DynamicBatching, TritonConfig


@dataclass
class InferenceRequest:
    """A single inference request inside the server."""

    request_id: str
    model_name: str
    inputs: Dict[str, np.ndarray]
    created_at: float = field(default_factory=time.time)
    outputs: Dict[str, np.ndarray] = field(default_factory=dict)
    error: str | None = None

    @property
    def batch_size(self) -> int:
        return next(iter(self.inputs.values())).shape[0] if self.inputs else 1


class Scheduler(ABC):
    """Abstract scheduler interface."""

    @abstractmethod
    def schedule(self, requests: List[InferenceRequest]) -> List[List[InferenceRequest]]:
        """Partition pending requests into batches for execution."""
        raise NotImplementedError


class DefaultScheduler(Scheduler):
    """No dynamic batching: each request forms its own batch."""

    def schedule(self, requests: List[InferenceRequest]) -> List[List[InferenceRequest]]:
        return [[req] for req in requests]


class DynamicBatcher(Scheduler):
    """Triton-style dynamic batcher.

    Groups pending requests into batches of up to ``max_batch_size``,
    preferring sizes listed in ``preferred_batch_size``.
    """

    def __init__(
        self,
        max_batch_size: int,
        preferred_batch_size: List[int] | None = None,
        max_queue_delay_microseconds: int = 0,
    ) -> None:
        self.max_batch_size = max_batch_size
        self.preferred_batch_size = sorted(preferred_batch_size or [])
        self.max_queue_delay_microseconds = max_queue_delay_microseconds

    @classmethod
    def from_config(cls, config: TritonConfig) -> "DynamicBatcher":
        if config.dynamic_batching is None:
            raise ValueError("Config does not enable dynamic_batching")
        return cls(
            max_batch_size=config.max_batch_size or 1,
            preferred_batch_size=config.dynamic_batching.preferred_batch_size,
            max_queue_delay_microseconds=config.dynamic_batching.max_queue_delay_microseconds,
        )

    def schedule(self, requests: List[InferenceRequest]) -> List[List[InferenceRequest]]:
        if not requests:
            return []
        batches: List[List[InferenceRequest]] = []
        queue = list(requests)
        while queue:
            first = queue[0]
            # Determine target batch size.
            target = self.max_batch_size
            if self.preferred_batch_size:
                for pbs in reversed(self.preferred_batch_size):
                    if pbs <= min(len(queue), self.max_batch_size):
                        target = pbs
                        break
            # If the oldest request has waited long enough, flush at least it.
            now = time.time()
            if (
                self.max_queue_delay_microseconds > 0
                and queue[0].created_at + self.max_queue_delay_microseconds / 1e6 <= now
            ):
                target = min(max(1, target), len(queue))
            # Build a compatible batch: all requests must share the same input
            # shapes (Triton requires this unless ragged batches are enabled).
            batch: List[InferenceRequest] = [first]
            for other in queue[1:]:
                if len(batch) >= target:
                    break
                if self._same_shape(first, other):
                    batch.append(other)
            for req in batch:
                queue.remove(req)
            batches.append(batch)
        return batches

    @staticmethod
    def _same_shape(a: InferenceRequest, b: InferenceRequest) -> bool:
        if set(a.inputs.keys()) != set(b.inputs.keys()):
            return False
        for name in a.inputs:
            if a.inputs[name].shape[1:] != b.inputs[name].shape[1:]:
                return False
        return True


def scheduler_for_config(config: TritonConfig) -> Scheduler:
    """Return the appropriate scheduler for a model config."""
    if config.ensemble_scheduling is not None:
        # Ensemble models use the EnsembleScheduler defined in ensemble.py.
        from .ensemble import EnsembleScheduler

        return EnsembleScheduler(config)
    if config.dynamic_batching is not None:
        return DynamicBatcher.from_config(config)
    return DefaultScheduler()
