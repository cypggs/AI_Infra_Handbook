"""Tests for the SLO calculator."""

from ai_sre_mini.slo import compute_availability_slo, parse_chat_request_counts


SAMPLE_METRICS = """
# HELP chat_requests_total Total chat requests
# TYPE chat_requests_total counter
chat_requests_total{model="gpt-mini",status="success"} 95.0
chat_requests_total{model="gpt-mini",status="error"} 5.0
"""


def test_parse_chat_request_counts():
    total, errors = parse_chat_request_counts(SAMPLE_METRICS)
    assert total == 100
    assert errors == 5


def test_compute_availability_slo():
    report = compute_availability_slo(100, 5, slo_target=0.99)
    assert report.total == 100
    assert report.errors == 5
    assert report.availability == 0.95
    assert report.burn_rate > 1.0
    assert report.status in {"critical", "warning", "elevated", "ok"}


def test_compute_availability_slo_no_data():
    report = compute_availability_slo(0, 0)
    assert report.status == "no data"
    assert report.availability == 1.0
