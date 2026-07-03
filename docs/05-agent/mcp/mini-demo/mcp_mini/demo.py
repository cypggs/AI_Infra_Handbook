"""End-to-end demo of the MCP Mini implementation."""

from __future__ import annotations

import io
import threading
import time
from contextlib import contextmanager
from typing import Any, Generator

from .client import MCPClient
from .llm_client import MockLLMClient
from .server import MockMCPServer
from .session import ClientSession
from .transport import InMemoryTransport


@contextmanager
def _wired(session: ClientSession, server: MockMCPServer) -> Generator[None, None, None]:
    """Run a background thread that pumps client requests to the server."""
    stop_event = threading.Event()
    transport = session.transport

    def _pump() -> None:
        while not stop_event.is_set():
            try:
                request = transport.pop_outgoing()
            except Exception:
                # No outgoing message available yet.
                if stop_event.is_set():
                    break
                time.sleep(0.001)
                continue
            response = server.handle(request)
            # Notifications have id=None; feed the sentinel response so the
            # pump loop stays clean and deterministic.
            transport.feed(response)

    pump_thread = threading.Thread(target=_pump, daemon=True)
    pump_thread.start()
    try:
        yield
    finally:
        stop_event.set()
        pump_thread.join(timeout=1.0)


def run_demo(output: io.StringIO | None = None) -> str:
    """Run the deterministic MCP mini demo and return the captured output."""
    out = output or io.StringIO()

    server = MockMCPServer()
    transport = InMemoryTransport()
    session = ClientSession(transport=transport)
    client = MCPClient(session=session)
    llm = MockLLMClient(default_answer="I'm not sure how to help with that.")

    with _wired(session, server):
        # Handshake
        client.initialize()
        out.write("Handshake complete.\n")

        # Show tools
        tools = client.list_tools()
        out.write(f"Tools: {[t['name'] for t in tools]}\n")

        # LLM turns user queries into tool calls.
        queries = [
            "Read the report",
            "Calculate 55 * 2",
            "What's the weather in Austin?",
        ]

        for query in queries:
            decision = llm.decide(query)
            out.write(f"\nUser: {query}\n")
            out.write(f"LLM decision: {decision}\n")

            if decision["action"] == "tool_call":
                result = client.call_tool(decision["tool"], decision["arguments"])
                content = result.get("content", [])
                text = content[0].get("text", "") if content else ""
                out.write(f"Tool result: {text}\n")
            else:
                out.write(f"Answer: {decision['answer']}\n")

        # Direct resource read
        resource = client.read_resource("file:///tmp/report.txt")
        resource_text = resource.get("contents", [{}])[0].get("text", "")
        out.write(f"\nResource: {resource_text}\n")

        # Prompt template
        prompt = client.get_prompt("summary", {"topic": "Q2 revenue"})
        prompt_text = prompt.get("messages", [{}])[0].get("content", {}).get("text", "")
        out.write(f"Prompt: {prompt_text}\n")

    return out.getvalue()


def main() -> int:
    """CLI entry point for the installed ``mcp-demo`` command."""
    print(run_demo(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
