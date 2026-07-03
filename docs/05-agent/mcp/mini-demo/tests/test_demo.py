"""Tests for the end-to-end demo."""

import io

from mcp_mini.demo import run_demo


def test_demo_completes_and_contains_expected_outputs():
    output = run_demo()
    assert "Q2 revenue" in output
    assert "110" in output
    assert "sunny" in output
    assert "read_file" in output
    assert "Handshake complete" in output


def test_demo_returns_string():
    out = io.StringIO()
    result = run_demo(output=out)
    assert isinstance(result, str)
    assert result == out.getvalue()
