"""MCP client implementation."""

from __future__ import annotations

from typing import Any

from .protocol import JSONRPCRequest, make_request
from .session import ClientSession
from .transport import InMemoryTransport


class MCPClient:
    """A synchronous MCP client over an in-memory transport."""

    def __init__(self, session: ClientSession | None = None) -> None:
        self.session = session or ClientSession()
        self._tools: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #

    def initialize(self) -> dict[str, Any]:
        """Perform the MCP initialize handshake."""
        result = self.session.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "mcp-mini-client",
                    "version": "0.1.0",
                },
                "capabilities": {},
            },
        )
        # Acknowledge initialization to the server.
        self.session.notify("notifications/initialized")
        return result

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    def list_tools(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """List tools exposed by the server."""
        if use_cache and self._tools is not None:
            return self._tools
        response = self.session.request("tools/list")
        self._tools = response.get("tools", [])
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a tool by name with the provided arguments."""
        return self.session.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )

    # ------------------------------------------------------------------ #
    # Resources
    # ------------------------------------------------------------------ #

    def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource by URI."""
        return self.session.request("resources/read", {"uri": uri})

    # ------------------------------------------------------------------ #
    # Prompts
    # ------------------------------------------------------------------ #

    def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get a prompt template by name."""
        return self.session.request(
            "prompts/get",
            {"name": name, "arguments": arguments or {}},
        )
