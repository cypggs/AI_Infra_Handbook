"""Tests for the AI SRE mini service."""

import re

from fastapi.testclient import TestClient

from ai_sre_mini.service import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_fields():
    response = client.get("/chat?q=hello")
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["model"] == "gpt-mini"
    assert isinstance(data["tokens"], int)
    assert isinstance(data["latency_ms"], (int, float))


def test_metrics_exposes_chat_counters():
    client.get("/chat?q=metrics")
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "chat_requests_total" in body
    assert "chat_request_duration_seconds" in body


def test_metrics_has_success_or_error():
    client.get("/chat?q=test")
    response = client.get("/metrics")
    body = response.text
    assert re.search(r'chat_requests_total\{model="gpt-mini",status="(success|error)"\}', body)
