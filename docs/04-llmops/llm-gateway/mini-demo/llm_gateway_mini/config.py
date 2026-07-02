from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml


@dataclass
class ProviderConfig:
    """Static configuration for one upstream provider."""

    name: str
    type: str
    endpoint: str
    weight: float = 1.0
    priority: int = 0
    latency_ms: float = 0.0
    failure_rate: float = 0.0
    failure_every_n: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """A model alias and the ordered list of providers that can serve it."""

    alias: str
    providers: List[str]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitConfig:
    """Token-bucket parameters."""

    requests_per_minute: int = 60
    burst: int = 10


@dataclass
class GatewayConfig:
    """Top-level gateway configuration loaded from YAML."""

    providers: Dict[str, ProviderConfig]
    models: Dict[str, ModelConfig]
    rate_limits: Dict[str, RateLimitConfig]
    routes: Dict[str, Any] = field(default_factory=dict)
    default_rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


def _load_providers(data: Dict[str, Any]) -> Dict[str, ProviderConfig]:
    providers: Dict[str, ProviderConfig] = {}
    for key, val in (data or {}).items():
        providers[key] = ProviderConfig(
            name=val.get("name", key),
            type=val.get("type", "openai"),
            endpoint=val.get("endpoint", ""),
            weight=float(val.get("weight", 1.0)),
            priority=int(val.get("priority", 0)),
            latency_ms=float(val.get("latency_ms", 0.0)),
            failure_rate=float(val.get("failure_rate", 0.0)),
            failure_every_n=int(val.get("failure_every_n", 0)),
            extra=val.get("extra", {}),
        )
    return providers


def _load_models(data: Dict[str, Any]) -> Dict[str, ModelConfig]:
    models: Dict[str, ModelConfig] = {}
    for key, val in (data or {}).items():
        models[key] = ModelConfig(
            alias=val.get("alias", key),
            providers=list(val.get("providers", [])),
            extra=val.get("extra", {}),
        )
    return models


def _load_rate_limits(data: Dict[str, Any]) -> Dict[str, RateLimitConfig]:
    limits: Dict[str, RateLimitConfig] = {}
    for key, val in (data or {}).items():
        limits[key] = RateLimitConfig(
            requests_per_minute=int(val.get("requests_per_minute", 60)),
            burst=int(val.get("burst", 10)),
        )
    return limits


def load_config(path: str) -> GatewayConfig:
    """Load gateway configuration from a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    providers = _load_providers(raw.get("providers", {}))
    models = _load_models(raw.get("models", {}))
    rate_limits = _load_rate_limits(raw.get("rate_limits", {}))
    default = rate_limits.get("default", RateLimitConfig())

    return GatewayConfig(
        providers=providers,
        models=models,
        rate_limits=rate_limits,
        routes=raw.get("routes", {}),
        default_rate_limit=default,
    )
