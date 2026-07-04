"""Runtime registry and matching logic."""
from __future__ import annotations

from kserve_mini.model import ModelFormat, RuntimeNotFound, ServingRuntime


class RuntimeRegistry:
    """In-memory registry of ServingRuntimes."""

    def __init__(self) -> None:
        self._runtimes: list[ServingRuntime] = []

    def register(self, runtime: ServingRuntime) -> None:
        self._runtimes.append(runtime)

    def resolve(self, model_format: str, requested: str | None = None) -> ServingRuntime:
        if requested:
            for runtime in self._runtimes:
                if runtime.name == requested:
                    return runtime
            raise RuntimeNotFound(f"requested runtime {requested!r} not found")

        candidates = [
            runtime
            for runtime in self._runtimes
            if any(
                fmt.name == model_format and fmt.auto_select
                for fmt in runtime.supported_formats
            )
        ]
        if not candidates:
            raise RuntimeNotFound(f"no runtime supports model format {model_format!r}")

        # Higher priority first, then deterministic name order.
        candidates.sort(key=lambda r: (-r.priority, r.name))
        return candidates[0]

    def list(self) -> list[ServingRuntime]:
        return list(self._runtimes)


def default_registry() -> RuntimeRegistry:
    """Factory for a registry with a few built-in runtimes."""
    registry = RuntimeRegistry()
    registry.register(
        ServingRuntime(
            name="kserve-sklearnserver",
            supported_formats=[ModelFormat(name="sklearn", priority=1)],
            image="kserve/sklearnserver:v0.13.0",
            args=["--model_name={{name}}", "--model_dir=/mnt/models"],
            protocol_versions=["v1", "v2"],
        )
    )
    registry.register(
        ServingRuntime(
            name="kserve-huggingfaceserver",
            supported_formats=[ModelFormat(name="huggingface", priority=1)],
            image="kserve/huggingfaceserver:v0.13.0",
            args=["--model_name={{name}}", "--model_dir=/mnt/models"],
            protocol_versions=["v2", "openai"],
        )
    )
    registry.register(
        ServingRuntime(
            name="custom-vllm",
            supported_formats=[ModelFormat(name="huggingface", auto_select=True, priority=2)],
            image="myregistry/vllm:v1.0",
            args=["--model=/mnt/models"],
            protocol_versions=["openai"],
        )
    )
    return registry
