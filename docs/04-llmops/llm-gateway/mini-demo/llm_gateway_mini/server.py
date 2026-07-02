from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from .auth_middleware import AuthMiddleware
from .config import GatewayConfig, RateLimitConfig
from .load_balancer import LatencyTracker
from .metrics import MetricsCollector
from .providers import BaseProvider, build_providers
from .rate_limiter import TokenBucket
from .retry_fallback import CircuitBreaker, FallbackChain, RetryPolicy
from .router import Router
from .transform import openai_to_provider, provider_to_openai


class GatewayApp:
    """Core application logic: auth, rate limits, routing, retries, metrics."""

    def __init__(
        self,
        config: GatewayConfig,
        providers: Optional[Dict[str, BaseProvider]] = None,
        auth: Optional[AuthMiddleware] = None,
        rate_limiter: Optional[TokenBucket] = None,
        router: Optional[Router] = None,
        router_strategy: str = "round_robin",
        retry_policy: Optional[RetryPolicy] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        self.config = config
        self.providers = providers or build_providers(config.providers)
        self.auth = auth or AuthMiddleware()
        self.rate_limiter = rate_limiter or TokenBucket.from_config(config.default_rate_limit)
        self.router = router or Router(config, self.providers, strategy=router_strategy)
        self.retry_policy = retry_policy or RetryPolicy()
        self.metrics = metrics or MetricsCollector()
        self.circuit_breakers = {
            provider: CircuitBreaker() for provider in self.providers.values()
        }
        self.latency_tracker = LatencyTracker()

    def handle_health(self) -> Dict[str, Any]:
        return {"status": "ok", "timestamp": int(time.time())}

    def handle_models(self) -> Dict[str, Any]:
        data = []
        for alias, model in self.config.models.items():
            data.append(
                {
                    "id": alias,
                    "object": "model",
                    "owned_by": ",".join(model.providers),
                }
            )
        return {"object": "list", "data": data}

    def handle_metrics(self) -> str:
        return self.metrics.prometheus_output()

    def _rate_limit_key(self, tenant: str, model: str) -> str:
        return f"{tenant}:{model}"

    def _route_and_call(self, tenant: str, request: Dict[str, Any]) -> Dict[str, Any]:
        model_alias = request.get("model")
        if not model_alias:
            return self._error(400, "Missing 'model' field")
        if model_alias not in self.config.models:
            return self._error(404, f"Unknown model: {model_alias}")

        if not self.rate_limiter.allow(self._rate_limit_key(tenant, model_alias)):
            self.metrics.record("gateway", model_alias, tenant, 429, 0.0, error=True)
            return self._error(429, "Rate limit exceeded")

        candidates = self.router.resolve(model_alias)
        primary = self.router.select(candidates)
        ordered = [primary] + [p for p in candidates if p is not primary]

        def invoke(provider: BaseProvider):
            provider_request = openai_to_provider(provider.config.type, request)
            start = time.monotonic()
            try:
                raw = provider.chat_completions(provider_request)
            finally:
                latency_ms = (time.monotonic() - start) * 1000.0
                self.router.record_latency(provider.config.name, latency_ms)
            return provider_to_openai(provider.config.name, request, raw), latency_ms

        try:
            provider, (response, latency_ms) = FallbackChain(
                ordered, self.retry_policy, breakers=self.circuit_breakers
            ).execute(invoke)
            self.metrics.record(
                provider.config.name, model_alias, tenant, 200, latency_ms, error=False
            )
            return response
        except Exception as exc:
            self.metrics.record("none", model_alias, tenant, 502, 0.0, error=True)
            return self._error(502, f"All providers failed: {exc}")

    def _error(self, status: int, message: str) -> Dict[str, Any]:
        return {
            "error": {"message": message, "type": "gateway_error", "code": status},
            "status": status,
        }

    def handle_chat_completions(self, tenant: str, body: bytes) -> Dict[str, Any]:
        try:
            request = json.loads(body)
        except json.JSONDecodeError as exc:
            return self._error(400, f"Invalid JSON: {exc}")
        return self._route_and_call(tenant, request)


class GatewayHandler(BaseHTTPRequestHandler):
    """HTTP facade around GatewayApp."""

    app: Optional[GatewayApp] = None

    def _send_json(self, status: int, data: Any) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, status: int, text: str) -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _get_tenant(self) -> Optional[str]:
        auth = self.headers.get("Authorization")
        tenant, _ = self.app.auth.validate(auth)
        return tenant

    def do_GET(self) -> None:
        tenant = self._get_tenant()
        if tenant is None:
            self._send_json(401, {"error": {"message": "Unauthorized", "code": 401}})
            return

        if self.path == "/health":
            self._send_json(200, self.app.handle_health())
        elif self.path == "/v1/models":
            self._send_json(200, self.app.handle_models())
        elif self.path == "/metrics":
            self._send_text(200, self.app.handle_metrics())
        else:
            self._send_json(404, {"error": {"message": "Not found", "code": 404}})

    def do_POST(self) -> None:
        tenant = self._get_tenant()
        if tenant is None:
            self._send_json(401, {"error": {"message": "Unauthorized", "code": 401}})
            return

        if self.path == "/v1/chat/completions":
            body = self._read_body()
            response = self.app.handle_chat_completions(tenant, body)
            status = response.pop("status", 200)
            self._send_json(status, response)
        else:
            self._send_json(404, {"error": {"message": "Not found", "code": 404}})

    def log_message(self, format: str, *args) -> None:
        pass


def make_server(
    app: GatewayApp, host: str = "127.0.0.1", port: int = 8080
) -> HTTPServer:
    handler = type("BoundGatewayHandler", (GatewayHandler,), {"app": app})
    return HTTPServer((host, port), handler)
