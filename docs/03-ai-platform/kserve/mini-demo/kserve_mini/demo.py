"""End-to-end demo script for the KServe mini demo."""
from __future__ import annotations

from kserve_mini.autoscaler import HorizontalPodAutoscaler
from kserve_mini.controller import KServeController
from kserve_mini.model import InferenceService, Predictor
from kserve_mini.registry import default_registry


def run_demo() -> dict:
    """Run the end-to-end demo and return a summary dict."""
    registry = default_registry()
    controller = KServeController(registry)

    # 1. User applies a sklearn InferenceService.
    isvc = InferenceService(
        name="sklearn-iris",
        namespace="default",
        predictor=Predictor(
            model_format="sklearn",
            storage_uri="gs://kfserving-examples/models/sklearn/1.0/model-1",
            min_replicas=1,
            max_replicas=5,
        ),
    )

    result = controller.reconcile(isvc)
    print(f"[Reconcile] runtime={result.runtime_name}, url={result.url}")
    print(f"[Deployment] {result.deployment.name}: replicas={result.deployment.replicas}, image={result.deployment.image}")
    print(f"[Service] {result.service.name}")
    print(f"[Ingress] {result.ingress.name}: host={result.ingress.host}")
    print(f"[HPA] {result.hpa.name}: min={result.hpa.min_replicas}, max={result.hpa.max_replicas}")

    # 2. Simulate load-based autoscaling.
    hpa = HorizontalPodAutoscaler(
        name=result.hpa.name,
        min_replicas=result.hpa.min_replicas,
        max_replicas=result.hpa.max_replicas,
        target_utilization=result.hpa.target_utilization,
    )
    replicas = result.deployment.replicas
    load_profile = [0.2, 0.8, 1.5, 2.2, 2.5, 0.4, 0.3]
    for rps in load_profile:
        load = hpa.simulate_load(replicas, rps * 10)
        decision = hpa.decide(replicas, load)
        replicas = decision.desired_replicas
        print(f"[Autoscaler] rps={rps*10:.0f} load={load:.2f} -> {decision.desired_replicas} replicas ({decision.reason})")

    # 3. Create gateway and send requests across protocols.
    gateway = controller.create_gateway(isvc, stable_version="sklearn-iris-v1")
    for protocol in ("v1", "v2", "openai"):
        if protocol == "openai":
            body = {"messages": [{"role": "user", "content": "hello"}]}
        elif protocol == "v2":
            body = {"inputs": [{"name": "input", "shape": [1, 4], "datatype": "FP32", "data": [1.0, 2.0, 3.0, 4.0]}]}
        else:
            body = {"instances": [[1.0, 2.0, 3.0, 4.0]]}
        resp = gateway.route(protocol, body)
        print(f"[{protocol.upper()}] status={resp.status_code}, body={resp.body}")

    # 4. Canary rollout.
    isvc.canary_traffic_percent = 30
    isvc.predictor.max_replicas = 10
    canary_result = controller.reconcile(isvc)
    gateway = controller.create_gateway(
        isvc,
        stable_version="sklearn-iris-v1",
        canary_version="sklearn-iris-v2",
    )
    print(f"\n[Canary] stable={gateway.weights['stable']}%, canary={gateway.weights['canary']}%")
    canary_counts = {"stable": 0, "canary": 0}
    for _ in range(1000):
        resp = gateway.route("v1", {"instances": [[1.0, 2.0, 3.0, 4.0]]})
        version = resp.body["model"]
        canary_counts["stable" if version == "sklearn-iris-v1" else "canary"] += 1
    print(f"[Canary traffic] stable={canary_counts['stable']}, canary={canary_counts['canary']}")

    summary = {
        "runtime": result.runtime_name,
        "url": result.url,
        "final_replicas": replicas,
        "canary_weights": gateway.weights,
        "canary_counts": canary_counts,
        "protocol_responses": {
            "v1": gateway.route("v1", {"instances": [[1.0, 2.0, 3.0, 4.0]]}).status_code,
            "v2": gateway.route("v2", {"inputs": [{"name": "input", "shape": [1, 4], "datatype": "FP32", "data": [1.0, 2.0, 3.0, 4.0]}]}).status_code,
            "openai": gateway.route("openai", {"messages": [{"role": "user", "content": "hello"}]}).status_code,
        },
    }
    print(f"\n[Summary] {summary}")
    return summary


if __name__ == "__main__":
    run_demo()
