"""Benchmark runner and report generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .agent import Agent
from .environment import ToolRegistry
from .evaluators import (
    CorrectnessEvaluator,
    CostEvaluator,
    LatencyEvaluator,
    RobustnessEvaluator,
    Score,
    ToolUseEvaluator,
)
from .llm_stub import StubLLM
from .tracer import Tracer


BUILTIN_DATASET: List[Dict[str, Any]] = [
    {
        "id": "math_1",
        "task": "What is 15 + 27?",
        "expected_answer": "42",
        "expected_tools": ["calculator"],
        "max_latency": 20,
        "max_cost": 50,
    },
    {
        "id": "fact_1",
        "task": "Who wrote Romeo and Juliet?",
        "expected_answer": "William Shakespeare",
        "expected_tools": ["search"],
        "max_latency": 20,
        "max_cost": 50,
    },
    {
        "id": "multi_1",
        "task": "What is the population of Paris divided by 2?",
        "expected_answer": "1050000",
        "expected_tools": ["search", "calculator"],
        "max_latency": 40,
        "max_cost": 80,
    },
    {
        "id": "fault_1",
        "task": "Fault injection: calculate 20 + 22 despite a failing calculator.",
        "expected_answer": "42",
        "expected_tools": ["calculator"],
        "max_latency": 30,
        "max_cost": 60,
        "fail_tool_budget": {"calculator": 1},
    },
]


@dataclass
class SampleResult:
    sample: Dict[str, Any]
    answer: str
    scores: List[Score] = field(default_factory=list)


class Benchmark:
    def __init__(self, agent: Agent, evaluators: List[Any]) -> None:
        self.agent = agent
        self.evaluators = evaluators

    def run(self, dataset: List[Dict[str, Any]]) -> List[SampleResult]:
        results: List[SampleResult] = []
        for sample in dataset:
            # Fresh tracer + tool registry per sample so each trace is independent.
            tracer = Tracer()
            agent = Agent(self.agent.llm, ToolRegistry(), tracer, max_steps=self.agent.max_steps)
            result = agent.run(sample["task"], sample)
            answer = result.answer or ""
            scores = [e.evaluate(sample, answer, result.trace) for e in self.evaluators]
            results.append(SampleResult(sample=sample, answer=answer, scores=scores))
        return results

    @staticmethod
    def report(results: List[SampleResult]) -> str:
        lines: List[str] = ["# Benchmark Report\n"]
        header = ["Sample", "Task", "Answer"] + [s.evaluator for s in results[0].scores]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "---|" * len(header))
        for r in results:
            cells = [r.sample["id"], r.sample["task"], r.answer]
            for s in r.scores:
                mark = "✅" if s.passed else "❌"
                cells.append(f"{mark} {s.value:.2f}")
            lines.append("| " + " | ".join(cells) + " |")

        lines.append("\n## Aggregate")
        names = [s.evaluator for s in results[0].scores]
        for name in names:
            passed = sum(1 for r in results for s in r.scores if s.evaluator == name and s.passed)
            total = len(results)
            lines.append(f"- **{name}**: {passed}/{total} passed ({passed/total*100:.1f}%)")
        return "\n".join(lines)


def run_builtin() -> List[SampleResult]:
    llm = StubLLM()
    tools = ToolRegistry()
    tracer = Tracer()
    agent = Agent(llm, tools, tracer, max_steps=5)
    evaluators = [
        CorrectnessEvaluator(),
        ToolUseEvaluator(),
        LatencyEvaluator(),
        CostEvaluator(),
        RobustnessEvaluator(),
    ]
    benchmark = Benchmark(agent, evaluators)
    return benchmark.run(BUILTIN_DATASET)
