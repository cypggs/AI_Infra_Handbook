"""MCP Mini Demo: a CPU-runnable, zero-external-API Model Context Protocol demo."""

from .client import MCPClient
from .llm_client import MockLLMClient
from .protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCErrorResponse,
)
from .server import MockMCPServer
from .session import ClientSession
from .transport import InMemoryTransport, StdioTransport

__all__ = [
    "MCPClient",
    "MockLLMClient",
    "MockMCPServer",
    "ClientSession",
    "InMemoryTransport",
    "StdioTransport",
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCErrorResponse",
]
