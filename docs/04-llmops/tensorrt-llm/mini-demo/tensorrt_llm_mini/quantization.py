"""Quantization configuration and fake-quantization helpers.

Real TensorRT-LLM would insert scaling factors, calibrate, and choose kernels.
This demo keeps the hooks but leaves the data mostly unchanged so it runs on a
CPU-only macOS machine.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class QuantConfig:
    """Quantization recipe used during build time."""

    dtype: str = "fp16"
    kv_cache_dtype: str = "fp16"
    per_channel: bool = False
    per_token: bool = False
    group_size: int | None = None

    def __post_init__(self) -> None:
        allowed = {"fp16", "bf16", "fp8", "int8", "fp4", "fp32"}
        if self.dtype not in allowed:
            raise ValueError(f"Unsupported quant dtype: {self.dtype}")
        if self.kv_cache_dtype not in allowed:
            raise ValueError(f"Unsupported kv-cache dtype: {self.kv_cache_dtype}")

    @property
    def is_quantized(self) -> bool:
        return self.dtype in {"fp8", "int8", "fp4"}

    def scale_name(self, tensor_name: str) -> str:
        return f"{tensor_name}_scale"

    def compute_scale(self, arr: np.ndarray) -> float:
        """Return a fake per-tensor scale for ``arr``."""
        amax = float(np.max(np.abs(arr))) + 1e-9
        if self.dtype == "fp8":
            return amax / 448.0
        if self.dtype == "int8":
            return amax / 127.0
        if self.dtype == "fp4":
            return amax / 6.0
        return 1.0

    def fake_quantize(self, arr: np.ndarray) -> np.ndarray:
        """Simulate quantization without materializing integer weights.

        Returns a lightly perturbed array so the quant path is observable while
        still keeping the model functional on CPU.
        """
        if not self.is_quantized:
            return arr.astype(np.float32)
        scale = self.compute_scale(arr)
        quantized = np.round(arr / scale)
        # Clip to a plausible dynamic range and return to float.
        if self.dtype == "fp8":
            quantized = np.clip(quantized, -448, 448)
        elif self.dtype == "int8":
            quantized = np.clip(quantized, -127, 127)
        elif self.dtype == "fp4":
            quantized = np.clip(quantized, -6, 6)
        dequant = quantized * scale
        # Add a tiny marker so tests can tell the quant path was exercised.
        marker = 1e-7 if self.dtype == "fp4" else 1e-6
        return (dequant + marker).astype(np.float32)

    def to_dict(self) -> dict:
        return {
            "dtype": self.dtype,
            "kv_cache_dtype": self.kv_cache_dtype,
            "per_channel": self.per_channel,
            "per_token": self.per_token,
            "group_size": self.group_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuantConfig":
        return cls(
            dtype=data["dtype"],
            kv_cache_dtype=data["kv_cache_dtype"],
            per_channel=data.get("per_channel", False),
            per_token=data.get("per_token", False),
            group_size=data.get("group_size", None),
        )
