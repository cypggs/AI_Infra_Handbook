"""Tests for the fake HPA."""
from __future__ import annotations

from kserve_mini.autoscaler import HorizontalPodAutoscaler


def test_scale_up_when_over_target() -> None:
    hpa = HorizontalPodAutoscaler(name="hpa", min_replicas=1, max_replicas=5, target_utilization=0.6)
    decision = hpa.decide(current_replicas=2, load=0.9)
    assert decision.desired_replicas == 3
    assert "load 0.90" in decision.reason


def test_scale_down_when_under_threshold() -> None:
    hpa = HorizontalPodAutoscaler(name="hpa", min_replicas=1, max_replicas=5, target_utilization=0.6)
    decision = hpa.decide(current_replicas=3, load=0.3)
    assert decision.desired_replicas == 2


def test_do_not_scale_below_min() -> None:
    hpa = HorizontalPodAutoscaler(name="hpa", min_replicas=2, max_replicas=5, target_utilization=0.6)
    decision = hpa.decide(current_replicas=2, load=0.1)
    assert decision.desired_replicas == 2
    assert decision.reason == "stable"


def test_do_not_scale_above_max() -> None:
    hpa = HorizontalPodAutoscaler(name="hpa", min_replicas=1, max_replicas=3, target_utilization=0.6)
    decision = hpa.decide(current_replicas=3, load=2.0)
    assert decision.desired_replicas == 3


def test_simulate_load() -> None:
    hpa = HorizontalPodAutoscaler(name="hpa", min_replicas=1, max_replicas=5, target_utilization=0.6)
    assert hpa.simulate_load(1, 5.0) == 0.5
    assert hpa.simulate_load(2, 25.0) == 1.25
    assert hpa.simulate_load(0, 1.0) == 1.0  # avoid division by zero
