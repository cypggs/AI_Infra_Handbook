"""Mock LLM client for deterministic tool-choice demonstrations."""

from __future__ import annotations

import re
from typing import Any


class MockLLMClient:
    """Deterministic LLM mock that picks tools based on keyword heuristics."""

    def __init__(self, default_answer: str = "I don't know.") -> None:
        self.default_answer = default_answer

    def decide(self, prompt: str) -> dict[str, Any]:
        """Return either a tool_call or a direct stop answer."""
        lowered = prompt.lower()

        if "read" in lowered or "report" in lowered:
            return {
                "action": "tool_call",
                "tool": "read_file",
                "arguments": {"path": "/tmp/report.txt"},
            }

        if "calculate" in lowered or self._contains_arithmetic(lowered):
            expression = self._extract_expression(lowered)
            return {
                "action": "tool_call",
                "tool": "calculator",
                "arguments": {"expression": expression or "1 + 1"},
            }

        if "weather" in lowered:
            city = self._extract_city(lowered) or "San Francisco"
            return {
                "action": "tool_call",
                "tool": "get_weather",
                "arguments": {"city": city},
            }

        return {
            "action": "stop",
            "answer": self.default_answer,
        }

    @staticmethod
    def _contains_arithmetic(text: str) -> bool:
        return bool(re.search(r"[\d\s]+[\+\-\*/][\d\s]+", text))

    @staticmethod
    def _extract_expression(text: str) -> str | None:
        # Extract a simple arithmetic expression from the prompt.
        match = re.search(r"([\d\s\+\-\*/\(\)\.]+)", text)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _extract_city(text: str) -> str | None:
        # Very naive city extractor for demo purposes.
        match = re.search(r"weather\s+(?:in|for)\s+([a-zA-Z\s]+)", text)
        if match:
            return match.group(1).strip()
        return None
