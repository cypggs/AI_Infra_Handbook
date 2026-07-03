"""End-to-end tests for the demo scenario."""

from tool_use_mini.demo import run_demo
from tool_use_mini.tool import reset_exchange_rate_service


def test_run_demo_produces_final_answer(capsys):
    """The full demo should run to completion and print the final answer."""
    reset_exchange_rate_service()
    answer = run_demo()
    captured = capsys.readouterr()

    assert "北京" in answer
    assert "7250" in answer
    assert "天气" in captured.out or "晴" in captured.out
    assert "汇率" in captured.out or "7.25" in captured.out


def test_run_demo_trace_includes_validation_error(capsys):
    """The printed trace should include the malformed calculate_rmb retry."""
    reset_exchange_rate_service()
    run_demo()
    captured = capsys.readouterr()
    assert "Validation failed" in captured.out or "validation" in captured.out.lower()
    assert "calculate_rmb" in captured.out
    assert "Final answer" in captured.out


def test_run_demo_repeatable():
    """The demo should be deterministic across runs."""
    reset_exchange_rate_service()
    answer1 = run_demo()
    reset_exchange_rate_service()
    answer2 = run_demo()
    assert answer1 == answer2
