"""KServe-style controller that reconciles InferenceService into K8s resources."""
from __future__ import annotations

from kserve_mini.autoscaler import HorizontalPodAutoscaler
from kserve_mini.dataplane import FakeModelServer
from kserve_mini.gateway import Gateway
from kserve_mini.model import (
    Deployment,
    HPA,
    InferenceService,
    Ingress,
    ReconcileResult,
    RuntimeNotFound,
    Service,
)
from kserve_mini.registry import RuntimeRegistry


class KServeController:
    """Reconciles an InferenceService into Deployment, Service, Ingress and HPA."""

    def __init__(self, registry: RuntimeRegistry) -> None:
        self.registry = registry

    def reconcile(self, isvc: InferenceService) -> ReconcileResult:
        runtime = self.registry.resolve(isvc.predictor.model_format, isvc.predictor.runtime)
        deployment = self._build_deployment(isvc, runtime)
        service = self._build_service(isvc)
        ingress = self._build_ingress(isvc)
        hpa = self._build_hpa(isvc)
        return ReconcileResult(
            deployment=deployment,
            service=service,
            ingress=ingress,
            hpa=hpa,
            url=f"http://{isvc.host}",
            runtime_name=runtime.name,
        )

    def _build_deployment(self, isvc: InferenceService, runtime) -> Deployment:
        args = [
            arg.replace("{{name}}", isvc.name).replace("{{namespace}}", isvc.namespace)
            for arg in runtime.args
        ]
        return Deployment(
            name=f"{isvc.name}-predictor",
            image=runtime.image,
            replicas=isvc.predictor.min_replicas,
            args=args,
            labels={"app": isvc.name, "runtime": runtime.name},
        )

    def _build_service(self, isvc: InferenceService) -> Service:
        return Service(
            name=f"{isvc.name}-predictor",
            selector={"app": isvc.name},
            ports=[{"name": "http", "port": 8080, "targetPort": 8080}],
        )

    def _build_ingress(self, isvc: InferenceService) -> Ingress:
        return Ingress(
            name=f"{isvc.name}-ingress",
            host=isvc.host,
            paths=["/v1/models", "/v2/models", "/openai/v1"],
            weights={"stable": 100 - isvc.canary_traffic_percent, "canary": isvc.canary_traffic_percent},
        )

    def _build_hpa(self, isvc: InferenceService) -> HPA:
        return HPA(
            name=f"{isvc.name}-hpa",
            min_replicas=isvc.predictor.min_replicas,
            max_replicas=isvc.predictor.max_replicas,
            target_utilization=0.6,
            metric="cpu",
        )

    def create_gateway(self, isvc: InferenceService, stable_version: str, canary_version: str | None = None) -> Gateway:
        """Build a Gateway for the reconciled InferenceService."""
        gateway = Gateway(host=isvc.host)
        runtime = self.registry.resolve(isvc.predictor.model_format, isvc.predictor.runtime)
        gateway.set_stable(FakeModelServer(name=stable_version, runtime_name=runtime.name))
        if canary_version:
            gateway.set_canary(
                FakeModelServer(name=canary_version, runtime_name=runtime.name),
                isvc.canary_traffic_percent,
            )
        return gateway
