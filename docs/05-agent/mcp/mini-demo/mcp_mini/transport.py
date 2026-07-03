"""Transport layers for MCP messages."""

from __future__ import annotations

from collections import deque
from typing import Any

from .protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCErrorResponse,
    parse_message,
)


class InMemoryTransport:
    """Queue-based in-memory transport for deterministic testing."""

    def __init__(self) -> None:
        self._incoming: deque[str] = deque()
        self._outgoing: deque[str] = deque()

    def send(self, message: JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse) -> None:
        """Enqueue a serialized message into outgoing buffer."""
        self._outgoing.append(message.serialize())

    def receive(self) -> JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse:
        """Dequeue and parse a message from the incoming buffer."""
        if not self._incoming:
            raise JSONRPCError(-32000, "No message available")
        raw = self._incoming.popleft()
        return parse_message(raw)

    def feed(self, message: JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse) -> None:
        """Inject a message into the incoming buffer (used by tests/peers)."""
        self._incoming.append(message.serialize())

    def pop_outgoing(self) -> JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse:
        """Dequeue and parse a message from the outgoing buffer.

        This lets a test harness read what the local peer sent and forward it
        to the remote peer.
        """
        if not self._outgoing:
            raise JSONRPCError(-32000, "No outgoing message available")
        raw = self._outgoing.popleft()
        return parse_message(raw)

    @property
    def outgoing(self) -> list[str]:
        """Return a snapshot of serialized outgoing messages."""
        return list(self._outgoing)

    @property
    def incoming_count(self) -> int:
        return len(self._incoming)

    @property
    def outgoing_count(self) -> int:
        return len(self._outgoing)


class StdioTransport:
    """Skeleton for a stdio-based transport.

    Not fully implemented because the demo runs in-memory and does not spawn
    subprocesses. It shows where read/write file descriptors would plug in.
    """

    def __init__(self, stdin: Any = None, stdout: Any = None) -> None:
        self.stdin = stdin
        self.stdout = stdout

    def send(self, message: JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse) -> None:
        """Write a serialized message followed by a newline to stdout."""
        line = message.serialize()
        if self.stdout is not None:
            self.stdout.write(line + "\n")
            self.stdout.flush()

    def receive(self) -> JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse:
        """Read a line from stdin and parse it as JSON-RPC."""
        if self.stdin is None:
            raise JSONRPCError(-32000, "StdioTransport: stdin not configured")
        line = self.stdin.readline()
        if not line:
            raise JSONRPCError(-32000, "StdioTransport: EOF")
        return parse_message(line.strip())
