import pytest

from llm_gateway_mini.load_balancer import (
    LatencyTracker,
    select_least_latency,
    select_priority,
    select_round_robin,
    select_weighted,
)


class DummyProvider:
    def __init__(self, name: str):
        self.config = type("Config", (), {"name": name})()


def test_latency_tracker_moving_average():
    tracker = LatencyTracker(window=3)
    tracker.record("a", 10)
    tracker.record("a", 20)
    tracker.record("a", 30)
    assert tracker.average("a") == 20.0
    tracker.record("a", 60)
    assert tracker.average("a") == pytest.approx(110 / 3, rel=1e-3)


def test_latency_tracker_best():
    tracker = LatencyTracker()
    tracker.record("fast", 5)
    tracker.record("slow", 100)
    assert tracker.best(["slow", "fast"]) == "fast"


def test_select_round_robin():
    c = ["a", "b"]
    choice, idx = select_round_robin(c, 0)
    assert choice == "a" and idx == 1
    choice, idx = select_round_robin(c, 1)
    assert choice == "b" and idx == 2
    choice, idx = select_round_robin(c, 2)
    assert choice == "a" and idx == 3


def test_select_weighted():
    def chooser(candidates, weights, k):
        # Always return the candidate whose weight is 1
        return [candidates[weights.index(1)]]

    assert select_weighted(["zero", "one"], [0, 1], chooser=chooser) == "one"


def test_select_weighted_rejects_zero_total():
    assert select_weighted(["a", "b"], [0, 0]) == "a"


def test_select_least_latency():
    tracker = LatencyTracker()
    tracker.record("b", 10)
    tracker.record("a", 50)
    candidates = [DummyProvider("a"), DummyProvider("b")]
    assert select_least_latency(candidates, tracker).config.name == "b"


def test_select_priority():
    assert select_priority(["x", "y"]) == "x"
    with pytest.raises(ValueError):
        select_priority([])
