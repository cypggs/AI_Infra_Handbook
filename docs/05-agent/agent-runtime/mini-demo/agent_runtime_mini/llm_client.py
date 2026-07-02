"""Deterministic mock LLM client that simulates function calling."""

import json
import re
from typing import Any


class MockLLMClient:
    """
    A deterministic LLM substitute.

    If the conversation already contains a tool result, it returns a final
    answer. Otherwise it inspects the latest user message and chooses a tool.
    """

    def __init__(self):
        self.call_count = 0

    def generate(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        self.call_count += 1
        has_observation = any(m.get("role") == "tool" for m in messages)
        last_user = self._last_user_content(messages)

        if has_observation:
            answer = self._final_answer(messages)
            return self._stop_response(answer)

        lowered = (last_user or "").lower()

        if "25*4+10" in lowered or "calculate" in lowered or "compute" in lowered:
            return self._tool_response(
                "calculator", {"expr": self._extract_expression(last_user)}
            )

        if "search" in lowered:
            query = self._extract_query(last_user)
            return self._tool_response("search", {"query": query})

        if "read_file" in lowered or "read" in lowered:
            path = self._extract_path(last_user)
            return self._tool_response("read_file", {"path": path})

        if "write_file" in lowered or "write" in lowered:
            path = self._extract_path(last_user)
            return self._tool_response("write_file", {"path": path, "content": "data"})

        return self._stop_response("I don't know how to handle that task.")

    def _last_user_content(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return str(message.get("content", ""))
        return ""

    def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "tool":
                return f"Final answer: {message.get('content', '')}"
        return "Final answer: done"

    def _tool_response(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": f"call_{self.call_count}",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    def _stop_response(self, content: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ]
        }

    @staticmethod
    def _extract_expression(text: str) -> str:
        match = re.search(r"[\d\+\-\*/\(\)\.\^ ]+", text)
        return (match.group(0).strip() if match else "0").replace(" ", "")

    @staticmethod
    def _extract_query(text: str) -> str:
        match = re.search(r"search(?:\s+for)?\s+(.+)", text, re.IGNORECASE)
        return match.group(1).strip() if match else text

    @staticmethod
    def _extract_path(text: str) -> str:
        match = re.search(r"(/[\w/\.\-]+)", text)
        return match.group(1) if match else "/tmp/demo.txt"

    def __repr__(self) -> str:  # pragma: no cover
        return f"MockLLMClient(calls={self.call_count})"
