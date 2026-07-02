"""Runtime: load an Engine and run single-request prefill/decode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from .dummy_backend import (
    add,
    attention,
    gelu,
    layer_norm,
    linear,
    lookup,
    sample_token,
)
from .engine import Engine


@dataclass
class SamplingParams:
    """Sampling parameters for generation."""

    max_tokens: int = 16
    temperature: float = 1.0
    top_k: int = 0
    top_p: float = 1.0
    eos_token_id: int = 0


class Runtime:
    """CPU runtime for a compiled Engine."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.build_config = engine.build_config
        self._rng = np.random.default_rng(42)

    def _make_kv_cache(self) -> Dict[str, Any]:
        """Create per-layer KV caches for the model."""
        cache: Dict[str, Any] = {}
        # Discover attention layers by looking at graph attributes.
        layers = {node["attrs"].get("layer") for node in self.engine.graph if node["op"] == "attention"}
        for layer in layers:
            if not layer:
                continue
            cache[layer] = {
                "cache_k": np.zeros(
                    (self._num_heads, self.build_config.max_seq_len, self._head_dim),
                    dtype=np.float32,
                ),
                "cache_v": np.zeros(
                    (self._num_heads, self.build_config.max_seq_len, self._head_dim),
                    dtype=np.float32,
                ),
                "cache_len": 0,
            }
        return cache

    @property
    def _num_heads(self) -> int:
        for node in self.engine.graph:
            if node["op"] == "attention":
                return int(node["attrs"]["num_heads"])
        return 1

    @property
    def _head_dim(self) -> int:
        # Infer from the qkv weight shape: (3*hidden, hidden) -> hidden = 3*hidden // 3
        for node in self.engine.graph:
            if node["op"] == "attention":
                qkv_name = self._find_qkv_weight(node)
                if qkv_name:
                    hidden = self.engine.weights[qkv_name].shape[1]
                    num_heads = int(node["attrs"]["num_heads"])
                    return hidden // num_heads
        return 8

    def _find_qkv_weight(self, attn_node: Dict[str, Any]) -> str | None:
        """Find the qkv linear weight feeding into an attention node."""
        # In the graph, attention node input comes from the qkv linear node.
        for node in self.engine.graph:
            if node["op"] == "linear" and attn_node["name"] in node.get("inputs", []):
                return node["attrs"].get("weight")
        return None

    def _sample(self, logits: np.ndarray, sp: SamplingParams) -> int:
        return sample_token(
            logits,
            temperature=sp.temperature,
            top_k=sp.top_k,
            top_p=sp.top_p,
            rng=self._rng,
        )

    def _execute_graph(self, input_ids: np.ndarray, kv_cache: Dict[str, Any]) -> np.ndarray:
        """Interpret the engine graph for a single request."""
        values: Dict[str, np.ndarray] = {"input_ids": input_ids}
        values.update(self.engine.weights)

        for node in self.engine.graph:
            op = node["op"]
            inputs = [values[inp] for inp in node["inputs"]]

            if op == "input":
                values[node["name"]] = values[node["name"]]
            elif op == "output":
                values[node["name"]] = inputs[0]
            elif op == "lookup":
                token_ids = inputs[0]
                table = inputs[1]
                values[node["name"]] = lookup(token_ids, table)
            elif op == "linear":
                x = inputs[0]
                w = inputs[1]
                b = inputs[2] if len(inputs) > 2 and node["attrs"].get("bias") else None
                values[node["name"]] = linear(x, w, b)
            elif op == "gelu":
                values[node["name"]] = gelu(inputs[0])
            elif op == "layer_norm":
                values[node["name"]] = layer_norm(inputs[0])
            elif op == "add":
                values[node["name"]] = add(inputs[0], inputs[1])
            elif op == "attention":
                layer = node["attrs"]["layer"]
                out, kv_cache[layer] = attention(inputs[0], int(node["attrs"]["num_heads"]), kv_cache[layer])
                values[node["name"]] = out
            elif op == "plugin":
                plugin_name = node["attrs"]["plugin"]
                plugin = self.engine.plugin_map[plugin_name]
                outputs = plugin.forward(inputs)
                values[node["name"]] = outputs[0]
            else:
                raise ValueError(f"Unsupported op: {op}")

        return values["logits"]

    def generate(
        self,
        prompt_ids: List[int],
        sampling_params: SamplingParams | None = None,
    ) -> List[int]:
        """Run prefill + decode until completion."""
        sp = sampling_params or SamplingParams()
        kv_cache = self._make_kv_cache()

        # Prefill
        input_ids = np.array([prompt_ids], dtype=np.int64)
        logits = self._execute_graph(input_ids, kv_cache)
        next_token = self._sample(logits[0, -1, :], sp)
        generated = [next_token]

        # Decode
        for _ in range(sp.max_tokens - 1):
            if next_token == sp.eos_token_id:
                break
            input_ids = np.array([[next_token]], dtype=np.int64)
            logits = self._execute_graph(input_ids, kv_cache)
            next_token = self._sample(logits[0, -1, :], sp)
            generated.append(next_token)

        return generated
