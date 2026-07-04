"""cgroup v2 resource limit simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CgroupV2:
    """Simplified cgroup v2 CPU/memory controller."""
    name: str
    cpu_weight: int = 100  # 1..10000
    cpu_max_nanos: int | None = None  # quota in nanos per period
    cpu_period_nanos: int = 100_000_000  # default 100ms
    memory_max: int | None = None  # bytes; None = unlimited
    processes: List[int] = field(default_factory=list)

    def cpu_share_fraction(self, total_weight: int) -> float:
        """Fraction of CPU when competing with total_weight."""
        if total_weight <= 0:
            return 0.0
        return self.cpu_weight / total_weight

    def cpu_limit_fraction(self) -> float | None:
        """Hard CPU limit as fraction of one core, or None if unlimited."""
        if self.cpu_max_nanos is None:
            return None
        if self.cpu_period_nanos <= 0:
            return None
        return self.cpu_max_nanos / self.cpu_period_nanos

    def effective_cpu_fraction(self, total_weight: int) -> float:
        """Effective CPU share considering both weight and hard cap."""
        share = self.cpu_share_fraction(total_weight)
        limit = self.cpu_limit_fraction()
        if limit is None:
            return share
        return min(share, limit)

    def request_memory(self, amount: int, current_usage: int) -> tuple[bool, int]:
        """Request memory. Returns (allowed, new_usage)."""
        if self.memory_max is None:
            return True, current_usage + amount
        if current_usage + amount <= self.memory_max:
            return True, current_usage + amount
        return False, current_usage

    def total_requested_cpu(self, sibling_groups: List["CgroupV2"]) -> Dict[str, float]:
        """Return per-cgroup effective CPU fraction for a set of siblings."""
        total_weight = sum(g.cpu_weight for g in sibling_groups)
        return {g.name: g.effective_cpu_fraction(total_weight) for g in sibling_groups}
