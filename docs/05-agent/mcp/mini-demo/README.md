# MCP Mini Demo

A CPU-runnable, zero-external-API demonstration of the Model Context Protocol
(MCP). It implements a tiny but complete JSON-RPC client/server pair with
in-memory transport, deterministic tool-choice, and full pytest coverage.

## What this demo shows

| Layer | File | Responsibility |
|-------|------|----------------|
| Protocol | `mcp_mini/protocol.py` | JSON-RPC 2.0 request/response/error message types and serialization |
| Transport | `mcp_mini/transport.py` | `InMemoryTransport` (queue-based) and `StdioTransport` skeleton |
| Server | `mcp_mini/server.py` | `MockMCPServer` handling initialize, tools, resources, prompts |
| Client | `mcp_mini/client.py` | `MCPClient` with handshake, list/call tools, read resources, get prompts |
| Session | `mcp_mini/session.py` | `ClientSession`: request-id mapping, in-flight tracking, timeout |
| LLM Mock | `mcp_mini/llm_client.py` | `MockLLMClient`: deterministic keyword-based tool selection |
| Demo | `mcp_mini/demo.py` | `run_demo()` end-to-end entry point |

## Install

```bash
cd /Users/case/AI_Infra_Handbook/docs/05-agent/mcp/mini-demo
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m mcp_mini.demo
# or, after install:
mcp-demo
```

Expected output includes:

```text
Handshake complete.
Tools: ['read_file', 'list_directory', 'calculator', 'get_weather']

User: Read the report
LLM decision: {'action': 'tool_call', 'tool': 'read_file', ...}
Tool result: Q2 revenue up 12%. (read from /tmp/report.txt)
...
Resource: Q2 revenue up 12%.
Prompt: Please summarize: Q2 revenue
```

## Run tests

```bash
pytest tests/ -v
```

## Programmatic usage

```python
from mcp_mini import MCPClient, MockMCPServer, ClientSession, InMemoryTransport

server = MockMCPServer()
transport = InMemoryTransport()
session = ClientSession(transport=transport)
client = MCPClient(session=session)

# Handshake
client.initialize()
while transport.outgoing_count:
    transport.feed(server.handle(transport.receive()))

# Call a tool
result = client.call_tool("calculator", {"expression": "55 * 2"})
while transport.outgoing_count:
    transport.feed(server.handle(transport.receive()))
print(result["content"][0]["text"])  # 110
```

## Differences from production MCP

| Aspect | This demo | Production MCP (e.g. `mcp` SDK) |
|--------|-----------|--------------------------------|
| Transport | In-memory queues | stdio or SSE over HTTP |
| Concurrency | Synchronous, single-threaded | Asyncio / multi-process |
| Tool choice | Keyword heuristic | Real LLM with function-calling API |
| Security | `eval` restricted to arithmetic | Sandboxed subprocess / user approval |
| Protocol version | Fixed string | Negotiated capability exchange |
| Persistence | None | Servers are real long-lived processes |
| Error handling | Minimal JSON-RPC codes | Rich logging, retries, streaming |

This demo is intentionally small so readers can trace a complete MCP flow
without network, API keys, or external dependencies.
