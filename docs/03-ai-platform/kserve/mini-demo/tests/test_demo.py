"""End-to-end tests for the demo."""
from __future__ import annotations

from kserve_mini.demo import run_demo


def test_run_demo() -> None:
    summary = run_demo()

    assert summary["runtime"] == "kserve-sklearnserver"
    assert summary["url"] == "http://sklearn-iris.default.example.com"
    assert summary["final_replicas"] >= 1
    assert summary["canary_weights"] == {"stable": 70, "canary": 30}
    assert summary["canary_counts"]["canary"] > 0
    assert summary["canary_counts"]["stable"] > 0
    assert all(code == 200 for code in summary["protocol_responses"].values())
