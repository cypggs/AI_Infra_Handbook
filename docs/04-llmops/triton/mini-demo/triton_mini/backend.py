"""Backend abstraction and a set of mock backends for the Mini Triton demo."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Type

import numpy as np

from .config_parser import TritonConfig


class BaseBackend(ABC):
    """Base class for all Triton backends in this demo."""

    @abstractmethod
    def execute(self, inputs: Dict[str, np.ndarray], config: TritonConfig) -> Dict[str, np.ndarray]:
        """Run inference on a batched set of inputs.

        Args:
            inputs: Mapping from input name to a NumPy array whose first
                dimension is the batch size.
            config: The model configuration used to determine output shapes.

        Returns:
            Mapping from output name to NumPy array.
        """
        raise NotImplementedError


class IdentityBackend(BaseBackend):
    """Returns the inputs unchanged or renamed according to output specs.

    Useful for preprocessing/postprocessing steps in an ensemble.
    """

    def execute(self, inputs: Dict[str, np.ndarray], config: TritonConfig) -> Dict[str, np.ndarray]:
        # If the config defines outputs, rename inputs to output names so that
        # ensemble steps can map tensors between models by name.
        if config.outputs and config.inputs and len(config.outputs) == len(config.inputs):
            return {
                out_spec.name: inputs[in_spec.name]
                for out_spec, in_spec in zip(config.outputs, config.inputs)
            }
        return dict(inputs)


class ClassificationBackend(BaseBackend):
    """A mock classification backend: softmax + argmax over the last dimension."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)

    def execute(self, inputs: Dict[str, np.ndarray], config: TritonConfig) -> Dict[str, np.ndarray]:
        input_name = next(iter(inputs))
        x = inputs[input_name].astype(np.float32)
        batch = x.shape[0]
        num_classes = config.outputs[0].dims[-1] if config.outputs else 10
        # Deterministic pseudo-logits based on mean input values.
        logits = np.tile(x.mean(axis=tuple(range(1, x.ndim))), (num_classes, 1)).T
        logits = logits + self._rng.standard_normal(logits.shape).astype(np.float32) * 0.1
        probs = self._softmax(logits)
        classes = np.argmax(probs, axis=1).astype(np.int64)
        scores = np.max(probs, axis=1).astype(np.float32)
        outputs: Dict[str, np.ndarray] = {}
        for spec in config.outputs:
            if "class" in spec.name.lower():
                outputs[spec.name] = classes.reshape([batch] + ([1] if spec.dims else []))
            else:
                outputs[spec.name] = probs.reshape([batch, num_classes])
        return outputs

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e / np.sum(e, axis=-1, keepdims=True)


class LLMBackend(BaseBackend):
    """A mock LLM backend that produces next-token ids from token-id inputs."""

    def __init__(self, seed: int = 7) -> None:
        self._rng = np.random.default_rng(seed)
        self.vocab_size = 64

    def execute(self, inputs: Dict[str, np.ndarray], config: TritonConfig) -> Dict[str, np.ndarray]:
        input_name = next(iter(inputs))
        token_ids = inputs[input_name]
        batch = token_ids.shape[0]
        # Use the last token of each sequence to seed deterministic output.
        seeds = token_ids[:, -1] if token_ids.ndim > 1 else token_ids
        next_tokens = np.array([self._sample(int(t)) for t in seeds], dtype=np.int64).reshape(batch, 1)
        outputs: Dict[str, np.ndarray] = {}
        for spec in config.outputs:
            if spec.dims == [1] or spec.dims == [-1, 1]:
                outputs[spec.name] = next_tokens
            else:
                # Fallback: produce logits-like output.
                logits = self._rng.standard_normal((batch, self.vocab_size)).astype(np.float32)
                outputs[spec.name] = logits
        return outputs

    def _sample(self, seed: int) -> int:
        return int(self._rng.integers(1, self.vocab_size, size=1)[0])


class ONNXRuntimeBackend(BaseBackend):
    """Mock ONNX Runtime backend that performs a fixed linear projection."""

    def __init__(self, seed: int = 3) -> None:
        self._rng = np.random.default_rng(seed)

    def execute(self, inputs: Dict[str, np.ndarray], config: TritonConfig) -> Dict[str, np.ndarray]:
        input_name = next(iter(inputs))
        x = inputs[input_name].astype(np.float32)
        batch = x.shape[0]
        in_features = int(np.prod(x.shape[1:]))
        out_features = config.outputs[0].dims[-1] if config.outputs else 10
        if not hasattr(self, "_weight") or self._weight.shape != (out_features, in_features):
            limit = np.sqrt(6.0 / (in_features + out_features))
            self._weight = self._rng.uniform(-limit, limit, (out_features, in_features)).astype(np.float32)
        flat = x.reshape(batch, in_features)
        out = flat @ self._weight.T
        outputs: Dict[str, np.ndarray] = {}
        for spec in config.outputs:
            target_shape = [batch] + ([d for d in spec.dims if d > 0] if spec.dims else [out_features])
            outputs[spec.name] = out.reshape(target_shape)
        return outputs


class BackendRegistry:
    """Registry mapping backend names to backend classes."""

    _registry: Dict[str, Type[BaseBackend]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: Type[BaseBackend]) -> None:
        cls._registry[name] = backend_cls

    @classmethod
    def create(cls, name: str) -> BaseBackend:
        if name not in cls._registry:
            raise ValueError(f"Unknown backend: {name}. Registered: {list(cls._registry)}")
        return cls._registry[name]()

    @classmethod
    def list_backends(cls) -> list[str]:
        return sorted(cls._registry.keys())


def _platform_to_backend(platform: str) -> str:
    mapping = {
        "onnxruntime_onnx": "onnxruntime",
        "tensorrt_plan": "tensorrt",
        "pytorch_libtorch": "pytorch",
    }
    return mapping.get(platform, platform)


def backend_for_config(config: TritonConfig) -> BaseBackend:
    """Create an appropriate backend for a model configuration."""
    name = config.backend or _platform_to_backend(config.platform)
    # Map common backend names to demo backends.
    if name in ("python", "identity", "preprocess", "postprocess"):
        return BackendRegistry.create("identity")
    if name in ("onnxruntime", "onnx"):
        return BackendRegistry.create("onnxruntime")
    if name in ("tensorrt_llm", "tensorrt-llm", "vllm"):
        return BackendRegistry.create("llm")
    if name in ("classification", "classify"):
        return BackendRegistry.create("classification")
    if name in BackendRegistry.list_backends():
        return BackendRegistry.create(name)
    # Default to identity for unknown backends so the demo stays runnable.
    return BackendRegistry.create("identity")


# Register built-in backends.
BackendRegistry.register("identity", IdentityBackend)
BackendRegistry.register("classification", ClassificationBackend)
BackendRegistry.register("llm", LLMBackend)
BackendRegistry.register("onnxruntime", ONNXRuntimeBackend)
BackendRegistry.register("python", IdentityBackend)
BackendRegistry.register("vllm", LLMBackend)
BackendRegistry.register("tensorrt_llm", LLMBackend)
BackendRegistry.register("tensorrt-llm", LLMBackend)

# Convenience aliases used by tests and demo.
MockBackend = ClassificationBackend
