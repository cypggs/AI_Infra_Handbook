"""KServe mini demo package."""

from kserve_mini.autoscaler import HorizontalPodAutoscaler
from kserve_mini.controller import KServeController
from kserve_mini.dataplane import FakeModelServer, Request, Response
from kserve_mini.gateway import Gateway
from kserve_mini.model import (
    Deployment,
    HPA,
    InferenceService,
    Ingress,
    ModelFormat,
    Predictor,
    ReconcileResult,
    RuntimeNotFound,
    Service,
    ServingRuntime,
)
from kserve_mini.registry import RuntimeRegistry, default_registry

__all__ = [
    "HorizontalPodAutoscaler",
    "KServeController",
    "FakeModelServer",
    "Request",
    "Response",
    "Gateway",
    "Deployment",
    "HPA",
    "InferenceService",
    "Ingress",
    "ModelFormat",
    "Predictor",
    "ReconcileResult",
    "RuntimeNotFound",
    "Service",
    "ServingRuntime",
    "RuntimeRegistry",
    "default_registry",
]
