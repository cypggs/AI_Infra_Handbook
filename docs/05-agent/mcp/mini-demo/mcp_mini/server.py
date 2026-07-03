"""Mock MCP server implementation."""

from __future__ import annotations

import json
from typing import Any, Callable

from .protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCErrorResponse,
    METHOD_NOT_FOUND,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    make_response,
    make_error,
)


Handler = Callable[[dict[str, Any]], Any]


class MockMCPServer:
    """A deterministic, in-memory MCP server for educational demos."""

    def __init__(self) -> None:
        self._initialized = False
        self._handlers: dict[str, Handler] = {
            "initialize": self._handle_initialize,
            "notifications/initialized": self._handle_notification,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "notifications/closed": self._handle_notification,
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def handle(self, message: JSONRPCRequest) -> JSONRPCResponse | JSONRPCErrorResponse:
        """Route a JSON-RPC request to its handler."""
        handler = self._handlers.get(message.method)
        if handler is None:
            return make_error(
                message.id,
                METHOD_NOT_FOUND,
                f"Method not found: {message.method}",
            )
        try:
            result = handler(message.params or {})
        except JSONRPCError as exc:
            return make_error(message.id, exc.code, exc.message, exc.data)
        except Exception as exc:  # pragma: no cover - safety net
            return make_error(message.id, INTERNAL_ERROR, str(exc))

        # Notifications do not return responses, but our transport layer
        # expects a response object for every request. Return a sentinel for
        # notifications so callers can decide to drop it.
        if result is None and message.id is None:
            return make_response(None, None)
        return make_response(message.id, result)

    # ------------------------------------------------------------------ #
    # Built-in handlers
    # ------------------------------------------------------------------ #

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "2024-11-05")
        self._initialized = True
        return {
            "protocolVersion": protocol_version,
            "serverInfo": {
                "name": "mcp-mini-server",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
        }

    def _handle_notification(self, params: dict[str, Any]) -> None:
        """Notifications have no response body."""
        return None

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read the contents of a file.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "list_directory",
                    "description": "List entries in a directory.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "calculator",
                    "description": "Evaluate a simple arithmetic expression.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string"},
                        },
                        "required": ["expression"],
                    },
                },
                {
                    "name": "get_weather",
                    "description": "Return current weather for a city.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                        },
                        "required": ["city"],
                    },
                },
            ]
        }

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not name:
            raise JSONRPCError(INVALID_PARAMS, "Missing tool name")

        if name == "read_file":
            path = arguments.get("path", "")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Q2 revenue up 12%. (read from {path})",
                    }
                ],
                "isError": False,
            }

        if name == "list_directory":
            path = arguments.get("path", "")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"['report.txt', 'notes.md'] (directory {path})",
                    }
                ],
                "isError": False,
            }

        if name == "calculator":
            expression = arguments.get("expression", "")
            try:
                # Safe, deterministic evaluation of a small arithmetic subset.
                value = self._evaluate_expression(expression)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": str(value),
                        }
                    ],
                    "isError": False,
                }
            except Exception as exc:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error evaluating expression: {exc}",
                        }
                    ],
                    "isError": True,
                }

        if name == "get_weather":
            city = arguments.get("city", "")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"The weather in {city} is sunny, 24°C.",
                    }
                ],
                "isError": False,
            }

        raise JSONRPCError(METHOD_NOT_FOUND, f"Unknown tool: {name}")

    @staticmethod
    def _evaluate_expression(expression: str) -> Any:
        """Evaluate a restricted arithmetic expression deterministically."""
        allowed_names = {"__builtins__": {}}
        allowed_operators = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b if b != 0 else float("nan"),
            "//": lambda a, b: a // b if b != 0 else 0,
            "%": lambda a, b: a % b,
            "**": lambda a, b: a ** b,
        }
        # Tokenize with spaces to keep eval safe and simple.
        sanitized = " ".join(str(expression).split())
        if not sanitized:
            raise ValueError("empty expression")
        # Use ast.literal_eval-friendly restricted eval.
        code = compile(sanitized, "<string>", "eval")
        for node in code.co_names:
            if node not in allowed_names:
                raise ValueError(f"disallowed name: {node}")
        return eval(code, allowed_names, allowed_operators)  # noqa: S307

    def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": "file:///tmp/report.txt",
                    "name": "Q2 Report",
                    "mimeType": "text/plain",
                }
            ]
        }

    def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri")
        if uri == "file:///tmp/report.txt":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": "Q2 revenue up 12%.",
                    }
                ]
            }
        raise JSONRPCError(METHOD_NOT_FOUND, f"Resource not found: {uri}")

    def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompts": [
                {
                    "name": "summary",
                    "description": "Summarize provided text.",
                    "arguments": [
                        {
                            "name": "topic",
                            "description": "Topic to summarize.",
                            "required": True,
                        }
                    ],
                }
            ]
        }

    def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "summary":
            topic = arguments.get("topic", "the topic")
            return {
                "description": f"Summary prompt for {topic}",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Please summarize: {topic}",
                        },
                    }
                ],
            }
        raise JSONRPCError(METHOD_NOT_FOUND, f"Prompt not found: {name}")
