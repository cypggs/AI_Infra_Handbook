from __future__ import annotations

import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict

from .config import ProviderConfig


def _make_id(prefix: str) -> str:
    return f"{prefix}-{random.getrandbits(32):08x}"


def _last_user_content(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""


@dataclass
class ProviderResponse:
    """OpenAI-shaped chat completion response."""

    id: str
    object: str
    created: int
    model: str
    choices: list
    usage: dict
    provider: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": self.choices,
            "usage": self.usage,
            "provider": self.provider,
        }


class BaseProvider(ABC):
    """Abstract interface for an upstream LLM provider."""

    def __init__(
        self,
        config: ProviderConfig,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self._clock = clock
        self._sleep = sleep
        self._calls = 0
        self._lock = threading.Lock()

    def _maybe_fail(self) -> None:
        with self._lock:
            self._calls += 1
            count = self._calls

        cfg = self.config
        if cfg.failure_every_n and count % cfg.failure_every_n == 0:
            raise RuntimeError(f"Simulated deterministic failure on {cfg.name}")
        if cfg.failure_rate and random.random() < cfg.failure_rate:
            raise RuntimeError(f"Simulated random failure on {cfg.name}")

    def _simulate_latency(self) -> None:
        self._sleep(self.config.latency_ms / 1000.0)

    @abstractmethod
    def chat_completions(self, request: dict) -> dict:
        """Execute a chat completion request and return an OpenAI-shaped dict."""
        raise NotImplementedError

    def _build_response(self, request: dict, content: str) -> dict:
        model = request.get("model", "unknown")
        return ProviderResponse(
            id=_make_id("chatcmpl"),
            object="chat.completion",
            created=int(self._clock()),
            model=model,
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            provider=self.config.name,
        ).to_dict()


class OpenAIProvider(BaseProvider):
    def chat_completions(self, request: dict) -> dict:
        self._simulate_latency()
        self._maybe_fail()
        content = f"[OpenAI] {_last_user_content(request.get('messages', []))}"
        return self._build_response(request, content)


class vLLMProvider(BaseProvider):
    def chat_completions(self, request: dict) -> dict:
        self._simulate_latency()
        self._maybe_fail()
        content = f"[vLLM] {_last_user_content(request.get('messages', []))}"
        return self._build_response(request, content)


class TritonProvider(BaseProvider):
    def chat_completions(self, request: dict) -> dict:
        self._simulate_latency()
        self._maybe_fail()
        content = f"[Triton] {_last_user_content(request.get('messages', []))}"
        return self._build_response(request, content)


def build_providers(configs: Dict[str, ProviderConfig]) -> Dict[str, BaseProvider]:
    mapping = {
        "openai": OpenAIProvider,
        "vllm": vLLMProvider,
        "triton": TritonProvider,
    }
    providers: Dict[str, BaseProvider] = {}
    for key, cfg in configs.items():
        cls = mapping.get(cfg.type, OpenAIProvider)
        providers[key] = cls(cfg)
    return providers
