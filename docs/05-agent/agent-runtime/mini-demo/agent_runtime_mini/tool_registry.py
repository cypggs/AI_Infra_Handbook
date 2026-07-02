"""Tool registry, @tool decorator, and built-in tools."""

import ast
import inspect
import json
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable


# In-memory filesystem shared across the process.
_FS: dict[str, str] = {}
_FS_LOCK = threading.Lock()


def _set_fs(path: str, content: str) -> None:
    with _FS_LOCK:
        _FS[path] = content


def _get_fs(path: str) -> str | None:
    with _FS_LOCK:
        return _FS.get(path)


def _clear_fs() -> None:
    with _FS_LOCK:
        _FS.clear()


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., Any]
    parameters: dict[str, Any]


class ToolRegistry:
    """Registry of tools with JSON-Schema metadata."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.name] = tool
        return tool

    def get_tool(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def dispatch(
        self,
        tool_call: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        name = tool_call.get("function", {}).get("name", "")
        arguments = tool_call.get("function", {}).get("arguments", "")
        tool = self.get_tool(name)
        parsed = self._parse_arguments(arguments)
        if "_context" in inspect.signature(tool.fn).parameters:
            parsed["_context"] = context or {}
        return tool.fn(**parsed)

    @staticmethod
    def _parse_arguments(arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            return json.loads(arguments)
        raise ValueError(f"Invalid arguments type: {type(arguments)}")


def _pytype_to_jsonschema(annotation: Any) -> dict[str, Any]:
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        if origin is list or annotation is list:
            item_type = args[0] if args else Any
            return {"type": "array", "items": _pytype_to_jsonschema(item_type)}
        if origin is dict or annotation is dict:
            return {"type": "object"}
        if origin is type or annotation is type:
            return {"type": "string"}
    if annotation in {str, "str"}:
        return {"type": "string"}
    if annotation in {int, "int"}:
        return {"type": "integer"}
    if annotation in {float, "float"}:
        return {"type": "number"}
    if annotation in {bool, "bool"}:
        return {"type": "boolean"}
    return {"type": "string"}


def _build_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name.startswith("_"):
            continue
        properties[param_name] = _pytype_to_jsonschema(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that registers function metadata for tool calling."""
    fn._tool_name = fn.__name__  # type: ignore[attr-defined]
    fn._tool_description = (fn.__doc__ or "").split("\n")[0].strip()  # type: ignore[attr-defined]
    fn._tool_parameters = _build_schema(fn)  # type: ignore[attr-defined]
    return fn


@tool
def calculator(expr: str, _context: dict[str, Any] | None = None) -> float:
    """Evaluate a safe arithmetic expression."""
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
        ast.UAdd,
    )
    node = ast.parse(expr, mode="eval")
    for child in ast.walk(node):
        if not isinstance(child, allowed_nodes):
            raise ValueError(f"Disallowed syntax: {type(child).__name__}")

    def _eval(n: ast.AST) -> float:
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.BinOp):
            left = _eval(n.left)
            right = _eval(n.right)
            if isinstance(n.op, ast.Add):
                return left + right
            if isinstance(n.op, ast.Sub):
                return left - right
            if isinstance(n.op, ast.Mult):
                return left * right
            if isinstance(n.op, ast.Div):
                return left / right
            if isinstance(n.op, ast.Pow):
                return left**right
        if isinstance(n, ast.UnaryOp):
            val = _eval(n.operand)
            if isinstance(n.op, ast.USub):
                return -val
            if isinstance(n.op, ast.UAdd):
                return val
        raise ValueError(f"Unsupported node: {type(n).__name__}")

    return _eval(node.body)


@tool
def search(query: str, _context: dict[str, Any] | None = None) -> str:
    """Search a mock knowledge base for the query."""
    lowered = query.lower()
    if "president" in lowered or "us president" in lowered:
        return "Mock search result: the current U.S. president is a placeholder."
    if "weather" in lowered:
        return "Mock search result: sunny, 72°F."
    return "Mock search result: no relevant results found."


@tool
def read_file(path: str, _context: dict[str, Any] | None = None) -> str:
    """Read a file from the in-memory filesystem."""
    content = _get_fs(path)
    if content is None:
        raise FileNotFoundError(f"No such file: {path}")
    return content


@tool
def write_file(path: str, content: str, _context: dict[str, Any] | None = None) -> str:
    """Write a file to the in-memory filesystem. Requires approval."""
    ctx = _context or {}
    if not ctx.get("approved"):
        raise PermissionError(
            f"write_file({path!r}) blocked: human approval required"
        )
    _set_fs(path, content)
    return f"Wrote {len(content)} bytes to {path}"


def default_tool_registry() -> ToolRegistry:
    """Return a registry with the built-in demo tools."""
    registry = ToolRegistry()
    for fn in (calculator, search, read_file, write_file):
        registry.register(
            Tool(
                name=fn._tool_name,  # type: ignore[attr-defined]
                description=fn._tool_description,  # type: ignore[attr-defined]
                fn=fn,
                parameters=fn._tool_parameters,  # type: ignore[attr-defined]
            )
        )
    return registry


__all__ = [
    "Tool",
    "ToolRegistry",
    "tool",
    "calculator",
    "search",
    "read_file",
    "write_file",
    "default_tool_registry",
]
