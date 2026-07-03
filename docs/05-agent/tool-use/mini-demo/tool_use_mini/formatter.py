"""Format tool results back into chat messages for the LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from tool_use_mini.executor import ToolResult


@dataclass
class ToolMessage:
    """A message carrying a tool result back to the model."""

    role: str
    tool_call_id: str
    name: str
    content: str


def format_results(results: List[ToolResult]) -> List[ToolMessage]:
    """Convert a list of tool results into model-facing tool messages."""
    messages: List[ToolMessage] = []
    for result in results:
        if result.success:
            content = json.dumps(result.data, ensure_ascii=False)
        else:
            content = json.dumps({"error": result.error}, ensure_ascii=False)
        messages.append(
            ToolMessage(
                role="tool",
                tool_call_id=result.call_id,
                name=result.name,
                content=content,
            )
        )
    return messages


def format_assistant_message(
    content: str,
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build an assistant message that includes emitted tool_calls."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
    }


def format_tool_message(result: ToolResult) -> Dict[str, Any]:
    """Build a raw tool message dict from a ToolResult."""
    if result.success:
        content = json.dumps(result.data, ensure_ascii=False)
    else:
        content = json.dumps({"error": result.error}, ensure_ascii=False)
    return {
        "role": "tool",
        "tool_call_id": result.call_id,
        "name": result.name,
        "content": content,
    }
