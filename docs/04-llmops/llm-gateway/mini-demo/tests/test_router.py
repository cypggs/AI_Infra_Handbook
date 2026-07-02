import pytest

from llm_gateway_mini.config import GatewayConfig, ModelConfig, ProviderConfig
from llm_gateway_mini.providers import BaseProvider
from llm_gateway_mini.router import Router


class FakeProvider(BaseProvider):
    def chat_completions(self, request: dict) -> dict:
        return {"provider": self.config.name}


def make_router(strategy: str = "round_robin"):
    providers = {
        "p1": FakeProvider(ProviderConfig(name="p1", type="openai", endpoint="", priority=5)),
        "p2": FakeProvider(
            ProviderConfig(name="p2", type="openai", endpoint="", weight=3, priority=2)
        ),
        "p3": FakeProvider(
            ProviderConfig(name="p3", type="openai", endpoint="", weight=1, priority=0)
        ),
    }
    config = GatewayConfig(
        providers={},
        models={"m1": ModelConfig(alias="m1", providers=["p1", "p2", "p3"])},
        rate_limits={},
    )
    return Router(config, providers, strategy=strategy)


def test_resolve_unknown_model():
    router = make_router()
    with pytest.raises(KeyError):
        router.resolve("missing")


def test_resolve_returns_candidates():
    router = make_router()
    candidates = router.resolve("m1")
    assert [p.config.name for p in candidates] == ["p1", "p2", "p3"]


def test_round_robin_cycles():
    router = make_router()
    seen = [router.select(router.resolve("m1")).config.name for _ in range(6)]
    assert seen == ["p1", "p2", "p3", "p1", "p2", "p3"]


def test_weighted_selection(monkeypatch):
    router = make_router("weighted")
    # Force weighted random to always return the second candidate (p2)
    monkeypatch.setattr(
        "llm_gateway_mini.load_balancer.random.choices", lambda c, weights, k: [c[1]]
    )
    assert router.select(router.resolve("m1")).config.name == "p2"


def test_least_latency_selects_best():
    router = make_router("least_latency")
    router.record_latency("p1", 100)
    router.record_latency("p2", 50)
    router.record_latency("p3", 10)
    assert router.select(router.resolve("m1")).config.name == "p3"


def test_priority_selects_lowest_value():
    router = make_router("priority")
    candidates = router.resolve("m1")
    assert candidates[0].config.name == "p3"
    assert router.select(candidates).config.name == "p3"
