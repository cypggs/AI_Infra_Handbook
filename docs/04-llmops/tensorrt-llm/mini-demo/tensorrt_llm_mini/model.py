"""Simplified neural-network modules used to define a tiny GPT model.

The modules define a symbolic execution graph that is consumed by the Builder.
Actual numeric computation lives in ``dummy_backend``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Tuple

import numpy as np


@dataclass
class Parameter:
    """A named weight tensor."""

    data: np.ndarray
    name: str | None = None

    @property
    def shape(self) -> Tuple[int, ...]:
        return tuple(self.data.shape)

    @property
    def dtype(self) -> np.dtype:
        return self.data.dtype


class Module:
    """Base class for all modules in the mini demo."""

    def __init__(self) -> None:
        object.__setattr__(self, "_modules", {})
        object.__setattr__(self, "_parameters", {})
        self.name: str | None = None

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, Module):
            self._modules[name] = value
        elif isinstance(value, Parameter):
            self._parameters[name] = value
        else:
            object.__setattr__(self, name, value)

    def __getattr__(self, name: str) -> Any:
        if name in self._modules:
            return self._modules[name]
        if name in self._parameters:
            return self._parameters[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def named_modules(self, prefix: str = "") -> Iterator[Tuple[str, Module]]:
        if prefix:
            yield prefix, self
        for key, module in self._modules.items():
            sub_prefix = f"{prefix}.{key}" if prefix else key
            yield from module.named_modules(sub_prefix)

    def named_parameters(self, prefix: str = "") -> Iterator[Tuple[str, Parameter]]:
        for key, param in self._parameters.items():
            yield f"{prefix}.{key}" if prefix else key, param
        for key, module in self._modules.items():
            sub_prefix = f"{prefix}.{key}" if prefix else key
            yield from module.named_parameters(sub_prefix)

    def apply_names(self, prefix: str = "") -> None:
        """Assign a human-readable name to every submodule."""
        if prefix:
            self.name = prefix
        for key, module in self._modules.items():
            sub_prefix = f"{prefix}.{key}" if prefix else key
            module.apply_names(sub_prefix)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.forward(*args, **kwargs)

    def forward(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def build_graph(self, builder: Any, x: str) -> str:
        """Add this module's ops to ``builder`` and return the output node id."""
        raise NotImplementedError


class ModuleList(Module, list):
    """A list of submodules that participates in ``named_modules``."""

    def __init__(self, modules: list[Module] | None = None) -> None:
        Module.__init__(self)
        list.__init__(self, modules or [])
        for idx, mod in enumerate(self):
            self._modules[str(idx)] = mod

    def append(self, module: Module) -> None:  # type: ignore[override]
        list.append(self, module)
        self._modules[str(len(self) - 1)] = module

    def build_graph(self, builder: Any, x: str) -> str:
        for module in self:
            x = module.build_graph(builder, x)
        return x


class Linear(Module):
    """Fully-connected layer."""

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool = True,
        name: str | None = None,
    ) -> None:
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.name = name
        limit = np.sqrt(6.0 / (in_features + out_features))
        rng = np.random.default_rng(0)
        w = rng.uniform(-limit, limit, (out_features, in_features))
        self.weight = Parameter(w.astype(np.float32), name=f"{name or 'linear'}.weight")
        if bias:
            b = np.zeros(out_features, dtype=np.float32)
            self.bias = Parameter(b, name=f"{name or 'linear'}.bias")
        else:
            self.bias = None

    def build_graph(self, builder: Any, x: str) -> str:
        weight_name = self.weight.name or f"{self.name}.weight"
        bias_name = self.bias.name if self.bias else None
        builder.register_weight(weight_name, self.weight.data)
        inputs = [x, weight_name]
        if bias_name:
            builder.register_weight(bias_name, self.bias.data)  # type: ignore[union-attr]
            inputs.append(bias_name)
        return builder.add_op(
            "linear",
            inputs=inputs,
            attrs={"weight": weight_name, "bias": bias_name},
        )


class Lookup(Module):
    """Token embedding lookup table."""

    def __init__(self, vocab_size: int, hidden_size: int, name: str = "embedding") -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.name = name
        table = np.random.default_rng(0).normal(0.0, 0.02, (vocab_size, hidden_size))
        self.weight = Parameter(table.astype(np.float32), name=f"{name}.weight")

    def build_graph(self, builder: Any, token_ids: str) -> str:
        weight_name = self.weight.name or f"{self.name}.weight"
        builder.register_weight(weight_name, self.weight.data)
        return builder.add_op(
            "lookup",
            inputs=[token_ids, weight_name],
            attrs={"weight": weight_name},
        )


class GELU(Module):
    """GELU activation (may be replaced by a plugin)."""

    def __init__(self, name: str = "gelu") -> None:
        super().__init__()
        self.name = name

    def build_graph(self, builder: Any, x: str) -> str:
        return builder.add_op("gelu", inputs=[x], attrs={})


class Attention(Module):
    """Multi-head self-attention."""

    def __init__(self, hidden_size: int, num_heads: int, name: str = "attn") -> None:
        super().__init__()
        assert hidden_size % num_heads == 0
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.name = name
        self.qkv = Linear(hidden_size, 3 * hidden_size, name=f"{name}.qkv")
        self.proj = Linear(hidden_size, hidden_size, name=f"{name}.proj")

    def build_graph(self, builder: Any, x: str) -> str:
        qkv = self.qkv.build_graph(builder, x)
        out = builder.add_op(
            "attention",
            inputs=[qkv],
            attrs={"num_heads": self.num_heads, "layer": self.name},
        )
        return self.proj.build_graph(builder, out)


class FeedForward(Module):
    """Position-wise feed-forward network (fc1 -> GELU -> fc2)."""

    def __init__(
        self,
        hidden_size: int,
        intermediate_size: int | None = None,
        name: str = "ff",
    ) -> None:
        super().__init__()
        self.name = name
        if intermediate_size is None:
            intermediate_size = 4 * hidden_size
        self.fc1 = Linear(hidden_size, intermediate_size, name=f"{name}.fc1")
        self.gelu = GELU(name=f"{name}.gelu")
        self.fc2 = Linear(intermediate_size, hidden_size, name=f"{name}.fc2")

    def build_graph(self, builder: Any, x: str) -> str:
        h = self.fc1.build_graph(builder, x)
        h = self.gelu.build_graph(builder, h)
        return self.fc2.build_graph(builder, h)


class TransformerBlock(Module):
    """A single transformer decoder layer."""

    def __init__(self, hidden_size: int, num_heads: int, name: str = "block") -> None:
        super().__init__()
        self.name = name
        self.attn = Attention(hidden_size, num_heads, name=f"{name}.attn")
        self.ff = FeedForward(hidden_size, name=f"{name}.ff")

    def build_graph(self, builder: Any, x: str) -> str:
        # Pre-norm style: x + attn(layer_norm(x))
        norm1 = builder.add_op("layer_norm", inputs=[x], attrs={"name": f"{self.name}.ln1"})
        attn_out = self.attn.build_graph(builder, norm1)
        residual1 = builder.add_op("add", inputs=[x, attn_out], attrs={})

        norm2 = builder.add_op("layer_norm", inputs=[residual1], attrs={"name": f"{self.name}.ln2"})
        ff_out = self.ff.build_graph(builder, norm2)
        return builder.add_op("add", inputs=[residual1, ff_out], attrs={})


class GPT(Module):
    """Tiny GPT-style language model."""

    def __init__(
        self,
        vocab_size: int = 64,
        hidden_size: int = 32,
        num_layers: int = 2,
        num_heads: int = 4,
        max_seq_len: int = 64,
    ) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.max_seq_len = max_seq_len
        self.embedding = Lookup(vocab_size, hidden_size, name="embedding")
        self.blocks = ModuleList(
            [TransformerBlock(hidden_size, num_heads, name=f"blocks.{i}") for i in range(num_layers)]
        )
        self.lm_head = Linear(hidden_size, vocab_size, bias=False, name="lm_head")
        self.apply_names()

    def forward(self, *args: Any, **kwargs: Any) -> Any:
        # Symbolic forward is not used; graph building is done by ``build_graph``.
        raise NotImplementedError("Use build_graph(builder, input_node) instead")

    def build_graph(self, builder: Any, token_ids: str) -> str:
        x = self.embedding.build_graph(builder, token_ids)
        x = self.blocks.build_graph(builder, x)
        return self.lm_head.build_graph(builder, x)
