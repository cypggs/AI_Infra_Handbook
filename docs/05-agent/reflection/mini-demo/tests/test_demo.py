"""Tests for the demo entry point."""

from reflection_mini.demo import run_demo


def test_run_demo_completes_and_finalizes_draft(capsys):
    run_demo()
    captured = capsys.readouterr()

    assert "Reflection Mini Demo" in captured.out
    assert "final_draft" in captured.out
    assert "Reflection trace:" in captured.out
