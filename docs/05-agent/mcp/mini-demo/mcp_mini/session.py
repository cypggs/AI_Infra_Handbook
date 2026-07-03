"""Client session with request-id mapping and in-flight tracking."""

from __future__ import annotations

import threading
import time
from typing import Any

from .protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCErrorResponse,
    INTERNAL_ERROR,
    make_request,
)
from .transport import InMemoryTransport


class ClientSession:
    """Synchronous MCP session backed by an in-memory transport.

    The session keeps a monotonically increasing request id and a mailbox of
    in-flight requests. Responses are matched by id.
    """

    def __init__(
        self,
        transport: InMemoryTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.transport = transport or InMemoryTransport()
        self.timeout = timeout
        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: dict[int | str, JSONRPCResponse | JSONRPCErrorResponse] = {}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _next_request_id(self) -> int:
        with self._lock:
            current = self._next_id
            self._next_id += 1
            return current

    def _send_request(self, id_: int | str | None, method: str, params: dict[str, Any] | None) -> None:
        request = make_request(id_, method, params)
        self.transport.send(request)

    def _wait_for_response(self, id_: int | str | None) -> JSONRPCResponse | JSONRPCErrorResponse:
        """Poll the transport until the matching response arrives."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if id_ in self._pending:
                return self._pending.pop(id_)

            try:
                message = self.transport.receive()
            except JSONRPCError as exc:
                if exc.code == -32000:
                    # No message available yet.
                    time.sleep(0.01)
                    continue
                raise

            if isinstance(message, JSONRPCResponse):
                if message.id == id_:
                    return message
                self._pending[message.id] = message
            elif isinstance(message, JSONRPCErrorResponse):
                if message.id == id_:
                    return message
                self._pending[message.id] = message
            # Requests originating from the server are not handled in this
            # minimal client.

        raise TimeoutError(f"Request {id_} timed out after {self.timeout}s")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and return its result."""
        id_ = self._next_request_id()
        self._send_request(id_, method, params)
        response = self._wait_for_response(id_)
        if isinstance(response, JSONRPCErrorResponse):
            raise JSONRPCError(response.code, response.message, response.data)
        return response.result

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        self._send_request(None, method, params)
