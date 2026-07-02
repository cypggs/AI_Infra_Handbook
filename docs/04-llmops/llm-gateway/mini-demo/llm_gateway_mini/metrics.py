from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List

DEFAULT_BUCKETS = [0, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]


@dataclass
class Histogram:
    """Simple histogram for Prometheus-style latency buckets."""

    buckets: List[float] = field(default_factory=lambda: list(DEFAULT_BUCKETS))
    _counts: Dict[float, int] = field(default_factory=lambda: defaultdict(int))
    _sum: float = 0.0
    _total: int = 0

    def observe(self, value: float) -> None:
        self._sum += value
        self._total += 1
        for bucket in self.buckets:
            if value <= bucket:
                self._counts[bucket] += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "sum": self._sum,
            "count": self._total,
            "buckets": dict(self._counts),
        }


@dataclass
class Counter:
    _counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def inc(self, key: str, value: int = 1) -> None:
        self._counts[key] += value

    def get(self, key: str) -> int:
        return self._counts.get(key, 0)

    def snapshot(self) -> Dict[str, int]:
        return dict(self._counts)


@dataclass
class MetricsCollector:
    """Prometheus-style metrics keyed by provider/model/tenant."""

    requests: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)
    status_codes: Counter = field(default_factory=Counter)
    latency: Dict[str, Histogram] = field(
        default_factory=lambda: defaultdict(lambda: Histogram())
    )

    def record(
        self,
        provider: str,
        model: str,
        tenant: str,
        status: int,
        latency_ms: float,
        error: bool = False,
    ) -> None:
        labels = f'provider="{provider}",model="{model}",tenant="{tenant}"'
        self.requests.inc(labels)
        self.status_codes.inc(f'status="{status}",provider="{provider}"')
        self.latency[labels].observe(latency_ms)
        if error:
            self.errors.inc(labels)

    def prometheus_output(self) -> str:
        lines: List[str] = []

        lines.append("# HELP gateway_requests_total Total requests routed by the gateway")
        lines.append("# TYPE gateway_requests_total counter")
        for labels, value in self.requests.snapshot().items():
            lines.append(f"gateway_requests_total{{{labels}}} {value}")

        lines.append("# HELP gateway_status_codes_total Total responses by status code")
        lines.append("# TYPE gateway_status_codes_total counter")
        for labels, value in self.status_codes.snapshot().items():
            lines.append(f"gateway_status_codes_total{{{labels}}} {value}")

        lines.append("# HELP gateway_errors_total Total errors")
        lines.append("# TYPE gateway_errors_total counter")
        for labels, value in self.errors.snapshot().items():
            lines.append(f"gateway_errors_total{{{labels}}} {value}")

        lines.append("# HELP gateway_latency_ms histogram Latency in milliseconds")
        lines.append("# TYPE gateway_latency_ms histogram")
        for labels, hist in self.latency.items():
            snap = hist.snapshot()
            for bucket in sorted(snap["buckets"].keys()):
                count = snap["buckets"][bucket]
                lines.append(f'gateway_latency_ms_bucket{{le="{bucket}",{labels}}} {count}')
            lines.append(f"gateway_latency_ms_sum{{{labels}}} {snap['sum']}")
            lines.append(f"gateway_latency_ms_count{{{labels}}} {snap['count']}")

        return "\n".join(lines)
