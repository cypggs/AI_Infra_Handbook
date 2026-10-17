"""Tests for the demo entry point."""
import io
import re
from contextlib import redirect_stdout

from training_reliability_mini import demo


def _capture() -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        demo.main()
    return buf.getvalue()


def test_demo_prints_all_five_scenarios():
    out = _capture()
    for i in range(1, 6):
        assert f"场景 {i}" in out
    assert "ETTR" in out
    assert "Daly" in out
    assert "bit" in out


def test_demo_is_deterministic():
    assert _capture() == _capture()


def test_demo_report_contains_sane_numbers():
    out = _capture()
    mtbf_row = re.search(r"\| 1024 \| ([0-9.]+) \|", out)
    assert mtbf_row is not None
    assert float(mtbf_row.group(1)) == 7.9
    cold = re.search(r"冷重启（全量 requeue） \| ([0-9.]+) \| ([0-9.]+)%", out)
    hot = re.search(r"热备（warm standby） \| ([0-9.]+) \| ([0-9.]+)%", out)
    assert cold and hot
    assert float(hot.group(2)) > float(cold.group(2))


