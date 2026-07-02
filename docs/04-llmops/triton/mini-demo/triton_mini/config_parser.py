"""A simplified `config.pbtxt` parser for the Mini Triton demo."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class TensorSpec:
    """Specification of an input or output tensor."""

    name: str
    data_type: str
    dims: List[int]
    reshape: List[int] = field(default_factory=list)
    is_shape_tensor: bool = False
    allow_ragged_batch: bool = False


@dataclass
class InstanceGroup:
    """Instance group configuration."""

    count: int = 1
    kind: str = "KIND_CPU"
    gpus: List[int] = field(default_factory=list)


@dataclass
class DynamicBatching:
    """Dynamic batching policy."""

    preferred_batch_size: List[int] = field(default_factory=list)
    max_queue_delay_microseconds: int = 0
    preferred_batch_size_aligned: bool = False
    preserve_ordering: bool = False


@dataclass
class EnsembleStep:
    """A single step in an ensemble scheduling block."""

    model_name: str
    model_version: int
    input_map: Dict[str, str] = field(default_factory=dict)
    output_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class EnsembleScheduling:
    """Ensemble scheduling configuration."""

    step: List[EnsembleStep] = field(default_factory=list)


@dataclass
class TritonConfig:
    """Structured view of a model configuration."""

    name: str = ""
    platform: str = ""
    backend: str = ""
    max_batch_size: int = 0
    inputs: List[TensorSpec] = field(default_factory=list)
    outputs: List[TensorSpec] = field(default_factory=list)
    instance_groups: List[InstanceGroup] = field(default_factory=list)
    dynamic_batching: DynamicBatching | None = None
    ensemble_scheduling: EnsembleScheduling | None = None
    parameters: Dict[str, str] = field(default_factory=dict)


class ConfigParser:
    """Parse a subset of Triton's `config.pbtxt` into `TritonConfig`."""

    _TOKEN_RE = re.compile(
        r'\s*(?:'
        r'"(?P<string>(?:[^"\\]|\\.)*)"'  # double-quoted string
        r"|'(?P<sstring>(?:[^'\\]|\\.)*)'"  # single-quoted string
        r"|(?P<number>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"  # number
        r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"  # identifier
        r"|(?P<punct>[:\{\}\[\],]))"  # punctuation
    )

    def parse_file(self, path: Path | str) -> TritonConfig:
        """Parse a `config.pbtxt` file."""
        raw = Path(path).read_text(encoding="utf-8")
        return self.parse_text(raw)

    def parse_text(self, text: str) -> TritonConfig:
        """Parse config text into `TritonConfig`."""
        tokens = self._tokenize(text)
        tree = self._parse_fields(tokens)
        return self._to_config(tree)

    # ------------------------------------------------------------------
    # Tokenizer
    # ------------------------------------------------------------------
    def _tokenize(self, text: str) -> List[Tuple[str, Any]]:
        tokens: List[Tuple[str, Any]] = []
        for m in self._TOKEN_RE.finditer(text):
            if m.lastgroup == "string":
                tokens.append(("STRING", m.group("string")))
            elif m.lastgroup == "sstring":
                tokens.append(("STRING", m.group("sstring")))
            elif m.lastgroup == "number":
                num = m.group("number")
                tokens.append(("NUMBER", float(num) if "." in num or "e" in num.lower() else int(num)))
            elif m.lastgroup == "ident":
                tokens.append(("IDENT", m.group("ident")))
            elif m.lastgroup == "punct":
                tokens.append(("PUNCT", m.group("punct")))
            else:
                # Should not happen because regex covers all non-whitespace.
                raise ValueError(f"Unexpected token: {m.group()}")
        tokens.append(("EOF", None))
        return tokens

    # ------------------------------------------------------------------
    # Recursive descent parser
    # ------------------------------------------------------------------
    def _parse_fields(self, tokens: List[Tuple[str, Any]]) -> Dict[str, Any]:
        """Parse fields until EOF or a closing brace is reached."""
        result: Dict[str, Any] = {}
        while tokens:
            tok_type, tok_val = tokens[0]
            if tok_type == "EOF" or (tok_type == "PUNCT" and tok_val in ("}", "]")):
                break
            if tok_type != "IDENT":
                raise ValueError(f"Expected identifier, got {tok_type} {tok_val}")
            key = tokens.pop(0)[1]
            # Colon is optional for message/list values in pbtxt.
            if tokens and tokens[0] == ("PUNCT", ":"):
                tokens.pop(0)
            value = self._parse_value(tokens)
            if key in result:
                existing = result[key]
                if not isinstance(existing, list):
                    existing = [existing]
                    result[key] = existing
                if isinstance(value, list):
                    existing.extend(value)
                else:
                    existing.append(value)
            else:
                result[key] = value
        return result

    def _parse_value(self, tokens: List[Tuple[str, Any]]) -> Any:
        if not tokens:
            raise ValueError("Unexpected end of input")
        tok_type, tok_val = tokens[0]
        if tok_type == "PUNCT" and tok_val == "[":
            return self._parse_list(tokens)
        if tok_type == "PUNCT" and tok_val == "{":
            return self._parse_message(tokens)
        if tok_type in ("STRING", "NUMBER", "IDENT"):
            tokens.pop(0)
            return tok_val
        raise ValueError(f"Unexpected value token: {tok_type} {tok_val}")

    def _parse_list(self, tokens: List[Tuple[str, Any]]) -> List[Any]:
        tokens.pop(0)  # consume '['
        items: List[Any] = []
        if tokens[0] == ("PUNCT", "]"):
            tokens.pop(0)
            return items
        # If first element is a message, parse a list of messages.
        if tokens[0] == ("PUNCT", "{"):
            while tokens[0] != ("PUNCT", "]"):
                items.append(self._parse_message(tokens))
                if tokens[0] == ("PUNCT", ","):
                    tokens.pop(0)
        else:
            while tokens[0] != ("PUNCT", "]"):
                items.append(self._parse_value(tokens))
                # Allow optional comma between list items.
                if tokens[0] == ("PUNCT", ","):
                    tokens.pop(0)
        if tokens[0] != ("PUNCT", "]"):
            raise ValueError("Expected ']' to close list")
        tokens.pop(0)
        return items

    def _parse_message(self, tokens: List[Tuple[str, Any]]) -> Dict[str, Any]:
        if tokens[0] != ("PUNCT", "{"):
            raise ValueError("Expected '{' to open message")
        tokens.pop(0)
        fields = self._parse_fields(tokens)
        if tokens[0] != ("PUNCT", "}"):
            raise ValueError("Expected '}' to close message")
        tokens.pop(0)
        return fields

    # ------------------------------------------------------------------
    # Convert parse tree to TritonConfig
    # ------------------------------------------------------------------
    def _to_config(self, tree: Dict[str, Any]) -> TritonConfig:
        config = TritonConfig(
            name=tree.get("name", ""),
            platform=tree.get("platform", ""),
            backend=tree.get("backend", ""),
            max_batch_size=int(tree.get("max_batch_size", 0)),
            inputs=[self._to_tensor_spec(item) for item in tree.get("input", [])],
            outputs=[self._to_tensor_spec(item) for item in tree.get("output", [])],
            instance_groups=[self._to_instance_group(item) for item in tree.get("instance_group", [])],
            parameters=self._to_parameters(tree.get("parameters", [])),
        )
        if "dynamic_batching" in tree:
            config.dynamic_batching = self._to_dynamic_batching(tree["dynamic_batching"])
        if "ensemble_scheduling" in tree:
            config.ensemble_scheduling = self._to_ensemble_scheduling(tree["ensemble_scheduling"])
        if not config.instance_groups:
            config.instance_groups.append(InstanceGroup())
        return config

    def _to_tensor_spec(self, item: Dict[str, Any]) -> TensorSpec:
        dims_raw = item.get("dims", [])
        dims = [int(d) if d != -1 else -1 for d in dims_raw]
        reshape_raw = item.get("reshape", [])
        reshape = [int(d) for d in reshape_raw]
        return TensorSpec(
            name=item.get("name", ""),
            data_type=item.get("data_type", ""),
            dims=dims,
            reshape=reshape,
            is_shape_tensor=bool(item.get("is_shape_tensor", False)),
            allow_ragged_batch=bool(item.get("allow_ragged_batch", False)),
        )

    def _to_instance_group(self, item: Dict[str, Any]) -> InstanceGroup:
        gpus_raw = item.get("gpus", [])
        gpus = [int(g) for g in gpus_raw] if isinstance(gpus_raw, list) else [int(gpus_raw)]
        return InstanceGroup(
            count=int(item.get("count", 1)),
            kind=item.get("kind", "KIND_CPU"),
            gpus=gpus,
        )

    def _to_dynamic_batching(self, item: Dict[str, Any]) -> DynamicBatching:
        pbs = item.get("preferred_batch_size", [])
        if isinstance(pbs, int):
            pbs = [pbs]
        return DynamicBatching(
            preferred_batch_size=[int(x) for x in pbs],
            max_queue_delay_microseconds=int(item.get("max_queue_delay_microseconds", 0)),
            preferred_batch_size_aligned=bool(item.get("preferred_batch_size_aligned", False)),
            preserve_ordering=bool(item.get("preserve_ordering", False)),
        )

    def _to_ensemble_scheduling(self, item: Dict[str, Any]) -> EnsembleScheduling:
        steps = []
        for step in item.get("step", []):
            steps.append(
                EnsembleStep(
                    model_name=step.get("model_name", ""),
                    model_version=int(step.get("model_version", -1)),
                    input_map=self._to_map(step.get("input_map", {})),
                    output_map=self._to_map(step.get("output_map", {})),
                )
            )
        return EnsembleScheduling(step=steps)

    def _to_map(self, raw: Any) -> Dict[str, str]:
        if isinstance(raw, dict):
            # Single map entry written as { key: "..." value: "..." }
            if "key" in raw and "value" in raw:
                return {str(raw["key"]): str(raw["value"])}
            return {str(k): str(v) for k, v in raw.items()}
        result: Dict[str, str] = {}
        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict):
                    key = entry.get("key")
                    val = entry.get("value")
                    if key is not None and val is not None:
                        result[str(key)] = str(val)
        return result

    def _to_parameters(self, raw: Any) -> Dict[str, str]:
        """Convert parameters block into a flat dict of string values."""
        result: Dict[str, str] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                result[str(k)] = self._param_value(v)
        elif isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict):
                    key = entry.get("key")
                    if key is None:
                        continue
                    val = entry.get("value")
                    result[str(key)] = self._param_value(val)
        return result

    def _param_value(self, v: Any) -> str:
        if isinstance(v, dict):
            if "string_value" in v:
                return str(v["string_value"])
            if "int_value" in v:
                return str(v["int_value"])
            if "bool_value" in v:
                return str(v["bool_value"])
        return str(v)
