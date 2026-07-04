"""Entry-point script for the benchmark mini-demo."""
from __future__ import annotations

from .benchmark import Benchmark, BUILTIN_DATASET
from .agent import Agent
from .environment import ToolRegistry
from .evaluators import (
    CorrectnessEvaluator,
    CostEvaluator,
    LatencyEvaluator,
    RobustnessEvaluator,
    ToolUseEvaluator,
)
from .llm_stub import StubLLM
from .tracer import Tracer


def run_all() -> None:
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
    results = benchmark.run(BUILTIN_DATASET)
    print(Benchmark.report(results))


def main() -> None:
    run_all()


if __name__ == "__main__":
    main()
