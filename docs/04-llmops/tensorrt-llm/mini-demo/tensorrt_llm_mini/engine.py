"""Serializable engine (the equivalent of a TensorRT plan)."""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .plugin import PluginBase
from .quantization import QuantConfig


@dataclass
class BuildConfig:
    """Build-time constraints and precision choices."""

    max_batch_size: int = 8
    max_input_len: int = 32
    max_seq_len: int = 64
    max_num_tokens: int = 256
    precision: str = "fp16"
    plugins: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "max_batch_size": self.max_batch_size,
            "max_input_len": self.max_input_len,
            "max_seq_len": self.max_seq_len,
            "max_num_tokens": self.max_num_tokens,
            "precision": self.precision,
            "plugins": list(self.plugins),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuildConfig":
        return cls(**data)


@dataclass
class Engine:
    """A compiled engine containing the execution graph, weights and plugins."""

    graph: list[dict[str, Any]]
    weights: dict[str, Any]
    plugin_map: dict[str, PluginBase]
    quant_config: QuantConfig
    build_config: BuildConfig
    metadata: dict[str, Any] = field(default_factory=dict)

    def serialize(self, path: str | Path) -> None:
        """Serialize the engine to disk (analogous to a TensorRT plan file)."""
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def deserialize(cls, path: str | Path) -> "Engine":
        """Load an engine that was previously serialized."""
        with open(path, "rb") as f:
            return pickle.load(f)

    def summary(self) -> dict[str, Any]:
        return {
            "num_ops": len(self.graph),
            "num_weights": len(self.weights),
            "num_plugins": len(self.plugin_map),
            "plugin_names": sorted({p.name for p in self.plugin_map.values()}),
            "precision": self.build_config.precision,
            "quant": self.quant_config.dtype,
        }
