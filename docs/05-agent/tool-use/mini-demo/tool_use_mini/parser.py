"""Parse raw model tool_calls into structured ToolCall objects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """A normalized tool call emitted by the model."""

    id: str
    name: str
    arguments: Dict[str, Any]
    raw: Optional[Dict[str, Any]] = None


@dataclass
class ParseError:
    """A structured error for a malformed tool call entry."""

    index: int
    raw: Any
    reason: str


def _coerce_arguments(value: Any, index: int) -> Dict[str, Any]:
    """Convert a variety of argument representations into a dict."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"arguments string is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"parsed arguments are not an object: {type(parsed).__name__}")
        return parsed
    raise ValueError(f"unsupported arguments type: {type(value).__name__}")


def parse_tool_calls(raw_calls: Any) -> tuple[List[ToolCall], List[ParseError]]:
    """Parse a list of raw tool_call entries into ToolCall objects.

    Tolerates two common shapes:
    - OpenAI style: {"id": "...", "function": {"name": "...", "arguments": "..."}}
    - Simplified style: {"id": "...", "name": "...", "arguments": {...}}
    """
    parsed: List[ToolCall] = []
    errors: List[ParseError] = []

    if raw_calls is None:
        return parsed, errors

    if not isinstance(raw_calls, list):
        errors.append(ParseError(index=0, raw=raw_calls, reason="tool_calls must be a list"))
        return parsed, errors

    for index, entry in enumerate(raw_calls):
        if not isinstance(entry, dict):
            errors.append(ParseError(index=index, raw=entry, reason="tool_call entry must be a dict"))
            continue

        # Resolve id/name/arguments regardless of wrapper shape.
        if "function" in entry and isinstance(entry["function"], dict):
            function_block = entry["function"]
            call_id = entry.get("id", f"call_{index}")
            name = function_block.get("name", "")
            arguments_raw = function_block.get("arguments", "{}")
        else:
            call_id = entry.get("id", f"call_{index}")
            name = entry.get("name", "")
            arguments_raw = entry.get("arguments", "{}")

        if not isinstance(name, str) or not name:
            errors.append(ParseError(index=index, raw=entry, reason="missing or invalid tool name"))
            continue

        try:
            arguments = _coerce_arguments(arguments_raw, index)
        except ValueError as exc:
            errors.append(ParseError(index=index, raw=entry, reason=str(exc)))
            continue

        parsed.append(ToolCall(id=str(call_id), name=name, arguments=arguments, raw=entry))

    return parsed, errors
