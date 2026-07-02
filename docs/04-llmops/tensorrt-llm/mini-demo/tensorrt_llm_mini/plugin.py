"""Plugin infrastructure and a few mock TensorRT-LLM-style plugins.

Plugins are registered via the ``@trtllm_plugin(name)`` decorator and can be
fused into the execution graph by the Builder.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, List, Type

import numpy as np


class PluginBase(ABC):
    """Base class for all plugins."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def shape_dtype_inference(self, inputs: List[Any]) -> List[tuple]:
        """Return a list of (shape, dtype) tuples for each plugin output."""
        ...

    @abstractmethod
    def forward(self, inputs: List[np.ndarray]) -> List[np.ndarray]:
        """Run the plugin on a list of input arrays."""
        ...

    def to_dict(self) -> dict:
        return {"name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "PluginBase":
        return cls(data["name"])


class PluginRegistry:
    """Global plugin registry populated by the decorator."""

    _registry: dict[str, Type[PluginBase]] = {}

    @classmethod
    def register(cls, name: str, plugin_cls: Type[PluginBase]) -> None:
        cls._registry[name] = plugin_cls

    @classmethod
    def get(cls, name: str) -> Type[PluginBase] | None:
        return cls._registry.get(name)

    @classmethod
    def list_plugins(cls) -> List[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        cls._registry.clear()


def trtllm_plugin(name: str) -> Any:
    """Class decorator that registers a plugin implementation under ``name``."""

    def decorator(plugin_cls: Type[PluginBase]) -> Type[PluginBase]:
        PluginRegistry.register(name, plugin_cls)
        plugin_cls.plugin_name = name  # type: ignore[attr-defined]
        return plugin_cls

    return decorator


@trtllm_plugin("GELUPlugin")
class GELUPlugin(PluginBase):
    """Approximate GELU activation."""

    def __init__(self) -> None:
        super().__init__("GELUPlugin")

    def shape_dtype_inference(self, inputs: List[Any]) -> List[tuple]:
        arr = inputs[0]
        return [(arr.shape, arr.dtype)]

    def forward(self, inputs: List[np.ndarray]) -> List[np.ndarray]:
        x = inputs[0]
        # GELU approximation used in GPT-2.
        c = math.sqrt(2.0 / math.pi)
        y = 0.5 * x * (1.0 + np.tanh(c * (x + 0.044715 * x**3)))
        return [y.astype(x.dtype)]


@trtllm_plugin("LookupPlugin")
class LookupPlugin(PluginBase):
    """Token-id to embedding-vector lookup."""

    def __init__(self) -> None:
        super().__init__("LookupPlugin")

    def shape_dtype_inference(self, inputs: List[Any]) -> List[tuple]:
        token_ids, table = inputs
        _, hidden = table.shape
        return [(token_ids.shape + (hidden,), table.dtype)]

    def forward(self, inputs: List[np.ndarray]) -> List[np.ndarray]:
        token_ids, table = inputs
        return [table[token_ids]]


@trtllm_plugin("RMSNormPlugin")
class RMSNormPlugin(PluginBase):
    """RMSNorm normalisation (demonstrates a second custom plugin flavour)."""

    def __init__(self, eps: float = 1e-6) -> None:
        super().__init__("RMSNormPlugin")
        self.eps = eps

    def shape_dtype_inference(self, inputs: List[Any]) -> List[tuple]:
        arr = inputs[0]
        return [(arr.shape, arr.dtype)]

    def forward(self, inputs: List[np.ndarray]) -> List[np.ndarray]:
        x, weight = inputs
        rms = np.sqrt(np.mean(x.astype(np.float64) ** 2, axis=-1, keepdims=True) + self.eps)
        return [(x / rms * weight).astype(x.dtype)]

    def to_dict(self) -> dict:
        return {"name": self.name, "eps": self.eps}

    @classmethod
    def from_dict(cls, data: dict) -> "RMSNormPlugin":
        return cls(eps=data.get("eps", 1e-6))
