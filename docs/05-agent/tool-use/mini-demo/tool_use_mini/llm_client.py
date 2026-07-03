"""Deterministic mock LLM client that emits scripted tool calls."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MockLLMResponse:
    """A normalized LLM response."""

    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"


class MockLLMClient:
    """Deterministic mock LLM that drives the demo scenario.

    The client advances an internal turn counter on each ``chat`` call and
    returns a pre-scripted response:

    1. Parallel ``get_weather`` + ``get_exchange_rate``.
    2. Malformed ``calculate_rmb`` (``rate`` as string) to exercise validation.
    3. Correct ``calculate_rmb``.
    4. Final natural-language answer.
    """

    def __init__(self, initial_turn: int = 0) -> None:
        self.turn = initial_turn
        self.messages: List[Dict[str, Any]] = []

    def chat(self, messages: Optional[List[Dict[str, Any]]] = None) -> MockLLMResponse:
        """Return the scripted response for the current turn.

        The caller owns the conversation history; this client only records the
        assistant responses it generates for inspection.
        """
        response = self._response_for_turn(self.turn)
        self.turn += 1

        # Record the assistant response so the conversation is inspectable.
        self.messages.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls,
            }
        )
        return response

    def _response_for_turn(self, turn: int) -> MockLLMResponse:
        if turn == 0:
            return MockLLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_weather_1",
                        "function": {
                            "name": "get_weather",
                            "arguments": json.dumps({"city": "北京"}, ensure_ascii=False),
                        },
                    },
                    {
                        "id": "call_rate_1",
                        "function": {
                            "name": "get_exchange_rate",
                            "arguments": json.dumps(
                                {"from_currency": "USD", "to_currency": "CNY"},
                                ensure_ascii=False,
                            ),
                        },
                    },
                ],
                finish_reason="tool_calls",
            )

        if turn == 1:
            # Malformed: rate is a string instead of a number.
            return MockLLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_calc_1",
                        "function": {
                            "name": "calculate_rmb",
                            "arguments": json.dumps(
                                {"amount_usd": 1000, "rate": "7.25"},
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
                finish_reason="tool_calls",
            )

        if turn == 2:
            return MockLLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_calc_2",
                        "function": {
                            "name": "calculate_rmb",
                            "arguments": json.dumps(
                                {"amount_usd": 1000, "rate": 7.25},
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
                finish_reason="tool_calls",
            )

        return MockLLMResponse(
            content=(
                "北京今天晴，气温 28℃，湿度 45%。\n"
                "美元兑人民币汇率为 7.25。\n"
                "1000 美元可以兑换 7250.00 人民币。"
            ),
            tool_calls=[],
            finish_reason="stop",
        )

    def reset(self) -> None:
        """Reset turn counter and conversation history."""
        self.turn = 0
        self.messages = []
