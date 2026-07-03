"""Tool definitions, registry, and built-in tool implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Tool:
    """A callable tool with a JSON Schema describing its parameters."""

    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Any]

    def to_dict(self) -> Dict[str, Any]:
        """Return an OpenAI-style function/tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Stores tools by name and invokes them safely."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        """Register a tool under its name."""
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Tool:
        """Fetch a tool by name, raising KeyError if missing."""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name!r}")
        return self._tools[name]

    def list_tools(self) -> List[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Invoke a registered tool with the supplied arguments."""
        tool = self.get(name)
        return tool.func(**arguments)

    def to_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return OpenAI-style tool definitions for all registered tools."""
        return [tool.to_dict() for tool in self._tools.values()]


def _build_object_schema(
    title: str,
    properties: Dict[str, Any],
    required: List[str],
    additional_properties: bool = False,
) -> Dict[str, Any]:
    """Build a minimal JSON Schema for an object with named properties."""
    return {
        "type": "object",
        "title": title,
        "properties": properties,
        "required": required,
        "additionalProperties": additional_properties,
    }


# ---- Built-in tool implementations -----------------------------------------

class _ExchangeRateService:
    """Stateful helper that simulates a flaky exchange-rate service."""

    def __init__(self) -> None:
        self.call_count = 0
        self.cached_rate = 7.25

    def get_rate(self, from_currency: str, to_currency: str) -> Dict[str, Any]:
        """Return exchange rate; fails on the first call, then returns cached."""
        self.call_count += 1
        from_cur = from_currency.upper()
        to_cur = to_currency.upper()
        if from_cur != "USD" or to_cur != "CNY":
            return {
                "success": False,
                "error": f"Unsupported currency pair: {from_cur}/{to_cur}",
            }
        if self.call_count == 1:
            return {
                "success": False,
                "error": "Exchange rate service temporarily unavailable",
                "fallback_rate": self.cached_rate,
            }
        return {
            "success": True,
            "from_currency": from_cur,
            "to_currency": to_cur,
            "rate": self.cached_rate,
        }


_exchange_rate_service = _ExchangeRateService()


def _get_weather(city: str) -> Dict[str, Any]:
    """Return deterministic weather data for a city."""
    city = city.strip()
    if city == "北京":
        return {
            "city": "北京",
            "temperature_c": 28,
            "condition": "晴",
            "humidity": 45,
        }
    return {
        "city": city,
        "temperature_c": 22,
        "condition": "多云",
        "humidity": 60,
    }


def _get_exchange_rate(from_currency: str, to_currency: str) -> Dict[str, Any]:
    """Return exchange rate (with a simulated first-call failure)."""
    return _exchange_rate_service.get_rate(from_currency, to_currency)


def _calculate_rmb(amount_usd: float, rate: float) -> Dict[str, Any]:
    """Convert USD to CNY using the provided rate."""
    return {
        "amount_usd": amount_usd,
        "rate": rate,
        "amount_rmb": round(amount_usd * rate, 2),
    }


def build_default_registry() -> ToolRegistry:
    """Create a registry with the demo tools pre-registered."""
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="get_weather",
            description="Get current weather for a city.",
            parameters=_build_object_schema(
                title="GetWeatherParameters",
                properties={
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 北京",
                    }
                },
                required=["city"],
            ),
            func=_get_weather,
        )
    )
    registry.register(
        Tool(
            name="get_exchange_rate",
            description="Get exchange rate between two currencies.",
            parameters=_build_object_schema(
                title="GetExchangeRateParameters",
                properties={
                    "from_currency": {
                        "type": "string",
                        "description": "Source currency code, e.g. USD",
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Target currency code, e.g. CNY",
                    },
                },
                required=["from_currency", "to_currency"],
            ),
            func=_get_exchange_rate,
        )
    )
    registry.register(
        Tool(
            name="calculate_rmb",
            description="Calculate how much RMB a USD amount can be exchanged for.",
            parameters=_build_object_schema(
                title="CalculateRMBParameters",
                properties={
                    "amount_usd": {
                        "type": "number",
                        "description": "Amount in USD",
                    },
                    "rate": {
                        "type": "number",
                        "description": "USD to CNY exchange rate",
                    },
                },
                required=["amount_usd", "rate"],
            ),
            func=_calculate_rmb,
        )
    )
    return registry


def reset_exchange_rate_service() -> None:
    """Reset the flaky exchange-rate service (useful for tests)."""
    global _exchange_rate_service
    _exchange_rate_service = _ExchangeRateService()
