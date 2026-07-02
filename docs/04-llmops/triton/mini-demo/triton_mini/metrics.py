"""Prometheus-style metrics collector for the Mini Triton demo."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class MetricValue:
    """A single labeled metric series."""

    labels: Dict[str, str]
    value: float = 0.0


@dataclass
class Counter:
    """A monotonically increasing counter."""

    name: str
    description: str
    values: Dict[str, MetricValue] = field(default_factory=dict)

    def inc(self, labels: Dict[str, str], amount: float = 1.0) -> None:
        key = self._key(labels)
        if key not in self.values:
            self.values[key] = MetricValue(labels=dict(labels))
        self.values[key].value += amount

    def _key(self, labels: Dict[str, str]) -> str:
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


@dataclass
class Histogram:
    """A histogram with configurable buckets."""

    name: str
    description: str
    buckets: List[float]
    counts: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(lambda: [0] * 5))
    sums: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.buckets:
            self.buckets = [1, 10, 100, 1000]

    def observe(self, labels: Dict[str, str], value: float) -> None:
        key = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        if key not in self.sums:
            self.sums[key] = 0.0
        self.sums[key] += value
        for i, bucket in enumerate(self.buckets):
            if value <= bucket:
                self.counts[key][i] += 1
                break


class MetricsCollector:
    """Collects request counters and latency histograms."""

    def __init__(self) -> None:
        self.request_count = Counter(
            "triton_mini_inference_count",
            "Total number of inference requests",
        )
        self.request_latency = Histogram(
            "triton_mini_inference_latency_microseconds",
            "Inference request latency in microseconds",
            buckets=[100, 1000, 10000, 100000],
        )
        self.batch_size = Histogram(
            "triton_mini_batch_size",
            "Executed batch sizes",
            buckets=[1, 2, 4, 8, 16],
        )

    def record_request(self, model: str, batch_size: int, latency_us: float) -> None:
        labels = {"model": model}
        self.request_count.inc(labels)
        self.request_latency.observe(labels, latency_us)
        self.batch_size.observe(labels, float(batch_size))

    def report(self) -> str:
        """Return a simple Prometheus exposition string."""
        lines: List[str] = []
        lines.append(f"# HELP {self.request_count.name} {self.request_count.description}")
        lines.append(f"# TYPE {self.request_count.name} counter")
        for mv in self.request_count.values.values():
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(mv.labels.items()))
            lines.append(f"{self.request_count.name}{{{label_str}}} {mv.value}")

        lines.append(f"# HELP {self.request_latency.name} {self.request_latency.description}")
        lines.append(f"# TYPE {self.request_latency.name} histogram")
        for key, total in self.request_latency.sums.items():
            labels = dict(pair.split("=", 1) for pair in key.split(","))
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            cumulative = 0
            for i, bucket in enumerate(self.request_latency.buckets):
                cumulative += self.request_latency.counts[key][i]
                lines.append(
                    f'{self.request_latency.name}_bucket{{{label_str},le="{bucket}"}} {cumulative}'
                )
            lines.append(f'{self.request_latency.name}_sum{{{label_str}}} {total}')
            lines.append(f'{self.request_latency.name}_count{{{label_str}}} {cumulative}')
        return "\n".join(lines) + "\n"
