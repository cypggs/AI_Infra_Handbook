from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from typing import Dict

from .config import GatewayConfig, ModelConfig
from .load_balancer import (
    LatencyTracker,
    select_least_latency,
    select_priority,
    select_round_robin,
    select_weighted,
)
from .providers import BaseProvider


@dataclass
class Router:
    """Resolve a model alias to candidate providers and select one by strategy."""

    config: GatewayConfig
    providers: Dict[str, BaseProvider]
    strategy: str = "round_robin"
    latency_tracker: LatencyTracker = field(default_factory=LatencyTracker)
    _indices: Dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def resolve(self, model_alias: str) -> list:
        model_cfg: ModelConfig | None = self.config.models.get(model_alias)
        if model_cfg is None:
            raise KeyError(f"Unknown model alias: {model_alias}")

        candidates = [self.providers[name] for name in model_cfg.providers if name in self.providers]
        if not candidates:
            raise ValueError(f"No providers available for model {model_alias}")

        if self.strategy == "priority":
            candidates.sort(key=lambda p: p.config.priority)
        return candidates

    def select(self, candidates: list) -> BaseProvider:
        if not candidates:
            raise ValueError("No candidates available")

        if self.strategy == "round_robin":
            key = tuple(sorted(p.config.name for p in candidates))
            with self._lock:
                idx = self._indices.get(key, 0)
                choice, next_idx = select_round_robin(candidates, idx)
                self._indices[key] = next_idx
            return choice

        if self.strategy == "weighted":
            weights = [p.config.weight for p in candidates]
            return select_weighted(candidates, weights)

        if self.strategy == "least_latency":
            return select_least_latency(candidates, self.latency_tracker)

        if self.strategy == "priority":
            return select_priority(candidates)

        raise ValueError(f"Unknown routing strategy: {self.strategy}")

    def record_latency(self, provider_name: str, latency_ms: float) -> None:
        self.latency_tracker.record(provider_name, latency_ms)
