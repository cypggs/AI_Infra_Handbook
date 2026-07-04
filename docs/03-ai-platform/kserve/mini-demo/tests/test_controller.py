"""Tests for KServeController reconcile."""
from __future__ import annotations

from kserve_mini.controller import KServeController
from kserve_mini.model import InferenceService, Predictor
from kserve_mini.registry import default_registry


def test_reconcile_sklearn_creates_resources() -> None:
    controller = KServeController(default_registry())
    isvc = InferenceService(
        name="iris",
        predictor=Predictor(
            model_format="sklearn",
            storage_uri="gs://models/iris",
            min_replicas=1,
            max_replicas=3,
        ),
    )
    result = controller.reconcile(isvc)

    assert result.runtime_name == "kserve-sklearnserver"
    assert result.url == "http://iris.default.example.com"
    assert result.deployment.name == "iris-predictor"
    assert result.deployment.image == "kserve/sklearnserver:v0.13.0"
    assert result.deployment.replicas == 1
    assert "--model_name=iris" in result.deployment.args
    assert result.service.name == "iris-predictor"
    assert result.ingress.name == "iris-ingress"
    assert result.ingress.host == "iris.default.example.com"
    assert result.hpa.name == "iris-hpa"
    assert result.hpa.min_replicas == 1
    assert result.hpa.max_replicas == 3


def test_reconcile_huggingface_selects_highest_priority_runtime() -> None:
    controller = KServeController(default_registry())
    isvc = InferenceService(
        name="llm",
        predictor=Predictor(model_format="huggingface", min_replicas=2, max_replicas=8),
    )
    result = controller.reconcile(isvc)
    assert result.runtime_name == "custom-vllm"
    assert result.deployment.replicas == 2


def test_reconcile_explicit_runtime_overrides_auto_select() -> None:
    controller = KServeController(default_registry())
    isvc = InferenceService(
        name="llm",
        predictor=Predictor(
            model_format="huggingface",
            runtime="kserve-huggingfaceserver",
            min_replicas=1,
            max_replicas=1,
        ),
    )
    result = controller.reconcile(isvc)
    assert result.runtime_name == "kserve-huggingfaceserver"


def test_reconcile_canary_weights() -> None:
    controller = KServeController(default_registry())
    isvc = InferenceService(
        name="iris",
        predictor=Predictor(model_format="sklearn", min_replicas=1, max_replicas=1),
        canary_traffic_percent=25,
    )
    result = controller.reconcile(isvc)
    assert result.ingress.weights == {"stable": 75, "canary": 25}
