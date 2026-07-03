"""Tests for the MCP client."""

from mcp_mini.client import MCPClient
from mcp_mini.demo import _wired
from mcp_mini.server import MockMCPServer
from mcp_mini.session import ClientSession
from mcp_mini.transport import InMemoryTransport


def test_client_initialize():
    transport = InMemoryTransport()
    session = ClientSession(transport=transport)
    client = MCPClient(session=session)
    server = MockMCPServer()

    with _wired(session, server):
        result = client.initialize()

    assert result["serverInfo"]["name"] == "mcp-mini-server"


def test_client_list_tools_and_cache():
    transport = InMemoryTransport()
    session = ClientSession(transport=transport)
    client = MCPClient(session=session)
    server = MockMCPServer()

    with _wired(session, server):
        client.initialize()
        tools = client.list_tools(use_cache=False)

    assert len(tools) == 4

    # Cached call should not produce new traffic.
    cached = client.list_tools(use_cache=True)
    assert cached is tools
    assert transport.outgoing_count == 0
