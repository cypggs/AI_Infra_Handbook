"""Simple SLO / burn-rate calculator using Prometheus exposition format."""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class SLOReport:
    total: int
    errors: int
    availability: float
    slo_target: float
    error_budget: float
    burn_rate: float
    status: str


def fetch_metrics(url: str = "http://127.0.0.1:8000/metrics") -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def parse_chat_request_counts(metrics_text: str) -> tuple[int, int]:
    """Return (total, errors) from chat_requests_total counters."""
    total = 0
    errors = 0
    for line in metrics_text.splitlines():
        if line.startswith("chat_requests_total{"):
            match = re.search(r'status="(success|error)"\}\s+([0-9.eE+-]+)', line)
            if match:
                value = int(float(match.group(2)))
                if match.group(1) == "success":
                    total += value
                elif match.group(1) == "error":
                    errors += value
                    total += value
    return total, errors


def compute_availability_slo(
    total: int,
    errors: int,
    slo_target: float = 0.99,
    observation_window_days: float = 30.0,
) -> SLOReport:
    """Compute availability SLO and burn rate.

    Burn rate = actual error rate / SLO error budget.
    A burn rate of 1 means the budget would be exactly exhausted at the end
    of the observation window.
    """
    if total <= 0:
        return SLOReport(
            total=0,
            errors=0,
            availability=1.0,
            slo_target=slo_target,
            error_budget=1.0 - slo_target,
            burn_rate=0.0,
            status="no data",
        )

    availability = (total - errors) / total
    actual_error_rate = errors / total
    error_budget = 1.0 - slo_target
    burn_rate = (actual_error_rate / error_budget) if error_budget > 0 else float("inf")

    if burn_rate >= 14.4:
        status = "critical"
    elif burn_rate >= 6.0:
        status = "warning"
    elif burn_rate >= 1.0:
        status = "elevated"
    else:
        status = "ok"

    return SLOReport(
        total=total,
        errors=errors,
        availability=availability,
        slo_target=slo_target,
        error_budget=error_budget,
        burn_rate=burn_rate,
        status=status,
    )


def run_demo() -> SLOReport:
    metrics_text = fetch_metrics()
    total, errors = parse_chat_request_counts(metrics_text)
    report = compute_availability_slo(total, errors)
    print(f"Total requests: {report.total}")
    print(f"Errors: {report.errors}")
    print(f"Availability: {report.availability:.4f}")
    print(f"SLO target: {report.slo_target:.4f}")
    print(f"Error budget: {report.error_budget:.4f}")
    print(f"Burn rate: {report.burn_rate:.2f}x")
    print(f"Status: {report.status}")
    return report


if __name__ == "__main__":
    run_demo()
