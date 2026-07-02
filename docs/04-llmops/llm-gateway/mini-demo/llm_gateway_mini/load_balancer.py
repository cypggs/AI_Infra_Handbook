from __future__ import annotations

import random
import threading
from collections import deque
from dataclasses import dataclass, field
from statistics import mean
from typing import Callable, List


@dataclass
class LatencyTracker:
    """Maintain a simple moving average of observed latency per provider."""

    window: int = 5
    _buckets: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, provider: str, latency_ms: float) -> None:
        with self._lock:
            if provider not in self._buckets:
                self._buckets[provider] = deque(maxlen=self.window)
            self._buckets[provider].append(latency_ms)

    def average(self, provider: str) -> float:
        with self._lock:
            bucket = self._buckets.get(provider)
            if not bucket:
                return float("inf")
            return mean(bucket)

    def best(self, provider_names: List[str]) -> str:
        with self._lock:
            def avg(name: str) -> float:
                bucket = self._buckets.get(name)
                return mean(bucket) if bucket else float("inf")

            return min(provider_names, key=avg)


def select_round_robin(candidates: list, index: int) -> tuple:
    if not candidates:
        raise ValueError("No candidates available")
    choice = candidates[index % len(candidates)]
    return choice, index + 1


def select_weighted(
    candidates: list, weights: List[float], chooser: Callable = random.choices
):
    if not candidates:
        raise ValueError("No candidates available")
    if len(weights) != len(candidates):
        raise ValueError("Weights length does not match candidates")
    if sum(weights) <= 0:
        return candidates[0]
    return chooser(candidates, weights=weights, k=1)[0]


def select_least_latency(candidates: list, tracker: LatencyTracker):
    if not candidates:
        raise ValueError("No candidates available")
    names = [p.config.name for p in candidates]
    best_name = tracker.best(names)
    for candidate in candidates:
        if candidate.config.name == best_name:
            return candidate
    return candidates[0]


def select_priority(candidates: list):
    if not candidates:
        raise ValueError("No candidates available")
    return candidates[0]
