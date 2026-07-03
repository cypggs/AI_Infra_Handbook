"""End-to-end test for the demo entry point."""
import io
from contextlib import redirect_stdout

from planning_mini.demo import run_demo


def test_demo_runs_to_success_and_prints_itinerary():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = run_demo()

    output = buffer.getvalue()
    assert result["success"] is True
    assert result["replan_count"] >= 1
    assert "北京>东京" in output
    assert "总花费" in output
