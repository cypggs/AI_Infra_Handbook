"""JSON-RPC 2.0 message types and MCP request/response helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class JSONRPCError(Exception):
    """Exception representing a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC error {code}: {message}")


@dataclass
class JSONRPCRequest:
    """A JSON-RPC 2.0 request object."""

    id: int | str | None
    method: str
    params: dict[str, Any] | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
        }
        if self.params is not None:
            data["params"] = self.params
        return data

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JSONRPCRequest":
        return cls(
            id=data.get("id"),
            method=data["method"],
            params=data.get("params"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


@dataclass
class JSONRPCResponse:
    """A JSON-RPC 2.0 response object."""

    id: int | str | None
    result: Any = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "result": self.result,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JSONRPCResponse":
        return cls(
            id=data.get("id"),
            result=data.get("result"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


@dataclass
class JSONRPCErrorResponse:
    """A JSON-RPC 2.0 error response object."""

    id: int | str | None
    code: int
    message: str
    data: Any = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            payload["data"] = self.data
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "error": payload,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JSONRPCErrorResponse":
        error = data.get("error", {})
        return cls(
            id=data.get("id"),
            code=error.get("code", -32603),
            message=error.get("message", "Internal error"),
            data=error.get("data"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


# JSON-RPC standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def make_request(id_: int | str | None, method: str, params: dict[str, Any] | None = None) -> JSONRPCRequest:
    """Convenience factory for JSON-RPC requests."""
    return JSONRPCRequest(id=id_, method=method, params=params)


def make_response(id_: int | str | None, result: Any) -> JSONRPCResponse:
    """Convenience factory for JSON-RPC responses."""
    return JSONRPCResponse(id=id_, result=result)


def make_error(
    id_: int | str | None,
    code: int,
    message: str,
    data: Any = None,
) -> JSONRPCErrorResponse:
    """Convenience factory for JSON-RPC error responses."""
    return JSONRPCErrorResponse(id=id_, code=code, message=message, data=data)


def parse_message(raw: str) -> JSONRPCRequest | JSONRPCResponse | JSONRPCErrorResponse:
    """Parse a raw JSON-RPC message into its typed representation."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JSONRPCError(PARSE_ERROR, "Parse error", str(exc)) from exc

    if not isinstance(data, dict):
        raise JSONRPCError(INVALID_REQUEST, "Invalid request: payload must be an object")

    if "error" in data:
        return JSONRPCErrorResponse.from_dict(data)
    if "method" in data:
        return JSONRPCRequest.from_dict(data)
    if "result" in data or "id" in data:
        return JSONRPCResponse.from_dict(data)

    raise JSONRPCError(INVALID_REQUEST, "Invalid request: unable to classify message")
