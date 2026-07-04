"""Deterministic tests for the benchmark + evaluation mini-demo."""
from __future__ import annotations

from benchmark_evaluation_mini.agent import Agent
from benchmark_evaluation_mini.benchmark import Benchmark, BUILTIN_DATASET, run_builtin
from benchmark_evaluation_mini.environment import ToolError, ToolRegistry
from benchmark_evaluation_mini.evaluators import (
    CorrectnessEvaluator,
    CostEvaluator,
    LatencyEvaluator,
    RobustnessEvaluator,
    ToolUseEvaluator,
)
from benchmark_evaluation_mini.llm_stub import StubLLM, parse_response
from benchmark_evaluation_mini.tracer import Tracer


# --------------------------------------------------------------------------- #
# LLM stub
# --------------------------------------------------------------------------- #
def test_parse_final_answer():
    text = "I know this.\nFinal Answer: 42"
    parsed = parse_response(text)
    assert parsed.final_answer == "42"
    assert parsed.action is None


def test_parse_action():
    text = "I should search.\nAction: search(foo)"
    parsed = parse_response(text)
    assert parsed.action.tool == "search"
    assert parsed.action.input == "foo"


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def test_calculator():
    tools = ToolRegistry()
    assert tools.calculator("15 + 27") == "42"
    assert tools.calculator("2100000 / 2") == "1050000"


def test_search():
    tools = ToolRegistry()
    assert "Shakespeare" in tools.search("Romeo and Juliet author")


def test_fault_injection():
    tools = ToolRegistry()
    try:
        tools.execute("calculator", "1+1", {"fail_tool_budget": {"calculator": 1}})
        assert False, "expected fault"
    except ToolError:
        pass
    # Second call succeeds.
    assert tools.execute("calculator", "1+1", {"fail_tool_budget": {"calculator": 1}}) == "2"


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
def _make_agent():
    return Agent(StubLLM(), ToolRegistry(), Tracer(), max_steps=5)


def test_agent_solves_math_task():
    agent = _make_agent()
    result = agent.run("What is 15 + 27?")
    assert result.answer == "42"
    assert any(c["tool"] == "calculator" for c in result.trace.tool_calls())


def test_agent_uses_search_for_fact():
    agent = _make_agent()
    result = agent.run("Who wrote Romeo and Juliet?")
    assert "Shakespeare" in result.answer
    assert any(c["tool"] == "search" for c in result.trace.tool_calls())


def test_agent_multi_step():
    agent = _make_agent()
    result = agent.run("What is the population of Paris divided by 2?")
    assert result.answer == "1050000"
    calls = result.trace.tool_calls()
    assert [c["tool"] for c in calls] == ["search", "calculator"]


# --------------------------------------------------------------------------- #
# Evaluators
# --------------------------------------------------------------------------- #
def test_correctness_evaluator():
    ev = CorrectnessEvaluator()
    sample = {"expected_answer": "42"}
    score = ev.evaluate(sample, "42", Tracer())
    assert score.passed
    score2 = ev.evaluate(sample, "24", Tracer())
    assert not score2.passed


def test_tool_use_evaluator():
    ev = ToolUseEvaluator()
    tracer = Tracer()
    with tracer.span("tool.call", tool="calculator", input="15+27"):
        pass
    score = ev.evaluate({"expected_tools": ["calculator"]}, "42", tracer)
    assert score.passed


def test_latency_evaluator():
    ev = LatencyEvaluator()
    tracer = Tracer()
    tracer.advance(5)
    score = ev.evaluate({"max_latency": 10}, "42", tracer)
    assert score.passed
    score2 = ev.evaluate({"max_latency": 2}, "42", tracer)
    assert not score2.passed


def test_cost_evaluator():
    ev = CostEvaluator()
    tracer = Tracer()
    with tracer.span("llm.complete", tokens=30):
        pass
    score = ev.evaluate({"max_cost": 50}, "42", tracer)
    assert score.passed


def test_robustness_evaluator():
    ev = RobustnessEvaluator()
    tracer = Tracer()
    tracer.add_event("tool.error", error="boom")
    score = ev.evaluate(
        {"expected_answer": "42", "fail_tool_budget": {"calculator": 1}},
        "42",
        tracer,
    )
    assert score.passed


# --------------------------------------------------------------------------- #
# Benchmark
# --------------------------------------------------------------------------- #
def test_benchmark_aggregates_scores():
    results = run_builtin()
    assert len(results) == len(BUILTIN_DATASET)
    for r in results:
        assert any(s.evaluator == "correctness" for s in r.scores)
    report = Benchmark.report(results)
    assert "Benchmark Report" in report
    assert "Aggregate" in report


def test_demo_runs_without_exception():
    from benchmark_evaluation_mini import demo
    demo.run_all()
