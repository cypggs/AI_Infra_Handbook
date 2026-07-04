"""Evaluators that turn traces and answers into scores."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .tracer import Tracer


@dataclass(frozen=True)
class Score:
    evaluator: str
    passed: bool
    value: float
    reason: str


class CorrectnessEvaluator:
    def __init__(self, case_sensitive: bool = False) -> None:
        self.case_sensitive = case_sensitive

    def evaluate(self, sample: Dict[str, Any], answer: Optional[str], trace: Tracer) -> Score:
        expected = sample.get("expected_answer", "")
        if answer is None:
            return Score("correctness", False, 0.0, "No final answer produced")
        a = answer if self.case_sensitive else answer.lower()
        e = expected if self.case_sensitive else expected.lower()
        passed = e in a
        return Score(
            "correctness",
            passed,
            1.0 if passed else 0.0,
            f"expected '{expected}' in answer '{answer}'" if passed else f"missing '{expected}'",
        )


class ToolUseEvaluator:
    def evaluate(self, sample: Dict[str, Any], answer: Optional[str], trace: Tracer) -> Score:
        expected = sample.get("expected_tools", [])
        calls = [c["tool"] for c in trace.tool_calls() if c["tool"]]
        if not expected:
            return Score("tool_use", True, 1.0, "No expected tools defined")
        matched = sum(1 for a, b in zip(calls, expected) if a == b)
        value = matched / max(len(expected), len(calls), 1)
        passed = value >= 1.0
        return Score(
            "tool_use",
            passed,
            value,
            f"expected {expected}, got {calls}",
        )


class LatencyEvaluator:
    def evaluate(self, sample: Dict[str, Any], answer: Optional[str], trace: Tracer) -> Score:
        threshold = sample.get("max_latency", 100)
        latency = trace.total_latency
        passed = latency <= threshold
        return Score(
            "latency",
            passed,
            latency,
            f"latency {latency} <= {threshold}" if passed else f"latency {latency} > {threshold}",
        )


class CostEvaluator:
    def evaluate(self, sample: Dict[str, Any], answer: Optional[str], trace: Tracer) -> Score:
        budget = sample.get("max_cost", 100)
        cost = trace.total_tokens()
        passed = cost <= budget
        return Score(
            "cost",
            passed,
            cost,
            f"cost {cost} <= {budget}" if passed else f"cost {cost} > {budget}",
        )


class RobustnessEvaluator:
    def evaluate(self, sample: Dict[str, Any], answer: Optional[str], trace: Tracer) -> Score:
        has_fault = bool(sample.get("fail_tool_budget"))
        if not has_fault:
            return Score("robustness", True, 1.0, "No fault injected")
        error_seen = trace.has_error_event()
        still_correct = sample.get("expected_answer", "") in (answer or "")
        passed = error_seen and still_correct
        return Score(
            "robustness",
            passed,
            1.0 if passed else 0.0,
            "recovered from injected fault" if passed else "did not recover from fault",
        )
