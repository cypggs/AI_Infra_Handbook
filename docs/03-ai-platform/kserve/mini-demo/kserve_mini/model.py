"""In-memory CRD-like data models for the KServe mini demo."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelFormat:
    name: str
    version: str | None = None
    auto_select: bool = True
    priority: int = 1


@dataclass
class ServingRuntime:
    name: str
    supported_formats: list[ModelFormat]
    image: str
    command: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    protocol_versions: list[str] = field(default_factory=lambda: ["v1"])

    @property
    def priority(self) -> int:
        # Highest priority among supported formats.
        return max((f.priority for f in self.supported_formats), default=1)


@dataclass
class Predictor:
    model_format: str
    runtime: str | None = None
    storage_uri: str | None = None
    min_replicas: int = 1
    max_replicas: int = 1
    resources: dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceService:
    name: str
    namespace: str = "default"
    predictor: Predictor = field(default_factory=lambda: Predictor(model_format="sklearn"))
    canary_traffic_percent: int = 0

    @property
    def host(self) -> str:
        return f"{self.name}.{self.namespace}.example.com"


@dataclass
class Deployment:
    name: str
    image: str
    replicas: int
    args: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Service:
    name: str
    selector: dict[str, str] = field(default_factory=dict)
    ports: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Ingress:
    name: str
    host: str
    paths: list[str] = field(default_factory=list)
    weights: dict[str, int] = field(default_factory=dict)


@dataclass
class HPA:
    name: str
    min_replicas: int
    max_replicas: int
    target_utilization: float
    metric: str = "cpu"


@dataclass
class ReconcileResult:
    deployment: Deployment
    service: Service
    ingress: Ingress
    hpa: HPA
    url: str
    runtime_name: str


class RuntimeNotFound(Exception):
    pass
