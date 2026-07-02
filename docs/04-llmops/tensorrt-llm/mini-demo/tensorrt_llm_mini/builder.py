"""Builder: converts a tiny GPT model into a compiled Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .engine import BuildConfig, Engine
from .model import GPT
from .plugin import PluginBase, PluginRegistry
from .quantization import QuantConfig


@dataclass
class Builder:
    """Symbolic builder that compiles a model definition into an Engine."""

    build_config: BuildConfig = field(default_factory=BuildConfig)
    quant_config: QuantConfig = field(default_factory=QuantConfig)
    plugin_registry: PluginRegistry = field(default_factory=lambda: PluginRegistry)

    def __post_init__(self) -> None:
        self._graph: List[Dict[str, Any]] = []
        self._weights: Dict[str, Any] = {}
        self._inputs: List[str] = []
        self._outputs: List[str] = []
        self._counter = 0

    def unique_name(self, prefix: str = "node") -> str:
        name = f"{prefix}_{self._counter}"
        self._counter += 1
        return name

    def add_input(self, name: str) -> str:
        self._inputs.append(name)
        self._graph.append({"op": "input", "name": name, "inputs": [], "attrs": {}})
        return name

    def add_output(self, name: str, node: str) -> None:
        self._outputs.append(name)
        self._graph.append({"op": "output", "name": name, "inputs": [node], "attrs": {}})

    def add_op(
        self,
        op_type: str,
        inputs: List[str],
        attrs: Dict[str, Any],
        name: str | None = None,
    ) -> str:
        node_name = name or self.unique_name(op_type)
        self._graph.append(
            {
                "op": op_type,
                "name": node_name,
                "inputs": list(inputs),
                "attrs": dict(attrs),
            }
        )
        return node_name

    def register_weight(self, name: str, data: Any) -> None:
        if name not in self._weights:
            self._weights[name] = self.quant_config.fake_quantize(data)

    def _replace_with_plugins(self) -> None:
        """Replace eligible ops with registered plugins."""
        requested = set(self.build_config.plugins)
        new_graph: List[Dict[str, Any]] = []
        for node in self._graph:
            if node["op"] == "gelu" and "GELUPlugin" in requested:
                node["op"] = "plugin"
                node["attrs"]["plugin"] = "GELUPlugin"
            elif node["op"] == "lookup" and "LookupPlugin" in requested:
                node["op"] = "plugin"
                node["attrs"]["plugin"] = "LookupPlugin"
            new_graph.append(node)
        self._graph = new_graph

    def build(self, model: GPT) -> Engine:
        """Compile ``model`` into an ``Engine``."""
        self._graph = []
        self._weights = {}
        self._inputs = []
        self._outputs = []
        self._counter = 0

        input_node = self.add_input("input_ids")
        output_node = model.build_graph(self, input_node)
        self.add_output("logits", output_node)
        self._replace_with_plugins()

        plugin_map: Dict[str, PluginBase] = {}
        for plugin_name in self.build_config.plugins:
            cls = self.plugin_registry.get(plugin_name)
            if cls is not None:
                plugin_map[plugin_name] = cls()

        return Engine(
            graph=self._graph,
            weights=self._weights,
            plugin_map=plugin_map,
            quant_config=self.quant_config,
            build_config=self.build_config,
            metadata={"num_params": sum(w.size for w in self._weights.values())},
        )
