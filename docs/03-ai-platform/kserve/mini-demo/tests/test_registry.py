"""Tests for RuntimeRegistry."""
from __future__ import annotations

import pytest

from kserve_mini.model import ModelFormat, RuntimeNotFound, ServingRuntime
from kserve_mini.registry import RuntimeRegistry


@pytest.fixture
def registry() -> RuntimeRegistry:
    r = RuntimeRegistry()
    r.register(
        ServingRuntime(
            name="rt-a",
            supported_formats=[ModelFormat(name="fmt", priority=1)],
            image="a:v1",
        )
    )
    r.register(
        ServingRuntime(
            name="rt-b",
            supported_formats=[ModelFormat(name="fmt", priority=2)],
            image="b:v1",
        )
    )
    r.register(
        ServingRuntime(
            name="rt-c",
            supported_formats=[ModelFormat(name="fmt", auto_select=False, priority=10)],
            image="c:v1",
        )
    )
    return r


def test_resolve_auto_select_highest_priority(registry: RuntimeRegistry) -> None:
    runtime = registry.resolve("fmt")
    assert runtime.name == "rt-b"


def test_resolve_explicit_runtime(registry: RuntimeRegistry) -> None:
    runtime = registry.resolve("fmt", requested="rt-a")
    assert runtime.name == "rt-a"


def test_resolve_explicit_runtime_not_found(registry: RuntimeRegistry) -> None:
    with pytest.raises(RuntimeNotFound):
        registry.resolve("fmt", requested="missing")


def test_resolve_no_auto_select_candidates(registry: RuntimeRegistry) -> None:
    registry2 = RuntimeRegistry()
    registry2.register(
        ServingRuntime(
            name="rt-d",
            supported_formats=[ModelFormat(name="fmt", auto_select=False)],
            image="d:v1",
        )
    )
    with pytest.raises(RuntimeNotFound):
        registry2.resolve("fmt")


def test_resolve_unknown_format(registry: RuntimeRegistry) -> None:
    with pytest.raises(RuntimeNotFound):
        registry.resolve("unknown-format")
