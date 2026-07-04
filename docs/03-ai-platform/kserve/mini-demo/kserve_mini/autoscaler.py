"""Simplified HPA-like autoscaler."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HPADecision:
    desired_replicas: int
    reason: str


class HorizontalPodAutoscaler:
    """Fake HPA that scales based on a normalized load signal.

    Load is expressed as a fraction of the target utilization:
    - load == 1.0 means exactly at target.
    - load > 1.0 means over target (scale up).
    - load < 1.0 means under target (scale down).
    """

    def __init__(
        self,
        name: str,
        min_replicas: int,
        max_replicas: int,
        target_utilization: float = 0.6,
        scale_down_stabilization: float = 0.8,
    ) -> None:
        self.name = name
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target_utilization = target_utilization
        self.scale_down_stabilization = scale_down_stabilization

    def decide(self, current_replicas: int, load: float) -> HPADecision:
        if load > self.target_utilization and current_replicas < self.max_replicas:
            return HPADecision(
                desired_replicas=min(current_replicas + 1, self.max_replicas),
                reason=f"load {load:.2f} > target {self.target_utilization:.2f}",
            )
        if (
            load < self.target_utilization * self.scale_down_stabilization
            and current_replicas > self.min_replicas
        ):
            return HPADecision(
                desired_replicas=max(current_replicas - 1, self.min_replicas),
                reason=f"load {load:.2f} < scale-down threshold",
            )
        return HPADecision(
            desired_replicas=current_replicas,
            reason="stable",
        )

    def simulate_load(self, current_replicas: int, requests_per_second: float) -> float:
        """Return normalized load given current capacity.

        Each replica can handle 10 rps. Load = rps / (replicas * 10).
        """
        capacity = max(current_replicas * 10.0, 1.0)
        return requests_per_second / capacity
