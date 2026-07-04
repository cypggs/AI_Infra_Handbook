"""Mock environment and tool registry for the deterministic agent."""
from __future__ import annotations

import ast
import operator
from typing import Any, Dict, Optional


class ToolError(Exception):
    """Raised when a tool execution fails."""


class ToolRegistry:
    """A small set of mock tools with optional fault injection."""

    def __init__(self, knowledge: Optional[Dict[str, str]] = None) -> None:
        self.knowledge = knowledge or {
            "romeo and juliet": "William Shakespeare wrote Romeo and Juliet.",
            "population of paris": "The population of Paris is about 2,100,000.",
        }
        self._failures: Dict[str, int] = {}

    def execute(self, name: str, args: str, scenario: Optional[Dict[str, Any]] = None) -> str:
        scenario = scenario or {}
        failure_budget = scenario.get("fail_tool_budget", {})
        if name in failure_budget and self._failures.get(name, 0) < failure_budget[name]:
            self._failures[name] = self._failures.get(name, 0) + 1
            raise ToolError(f"Injected fault: {name}({args})")

        handler = getattr(self, name, None)
        if handler is None:
            raise ToolError(f"Unknown tool: {name}")
        return handler(args)

    def search(self, query: str) -> str:
        key = query.lower()
        for topic, fact in self.knowledge.items():
            if topic in key:
                return fact
        return "No relevant information found."

    def calculator(self, expr: str) -> str:
        try:
            node = ast.parse(expr, mode="eval")
            value = self._eval_node(node.body)
            # Remove trailing .0 for integers.
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        except Exception as exc:
            raise ToolError(f"Invalid expression: {expr} ({exc})")

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_map = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
            }
            op_func = op_map.get(type(node.op))
            if op_func is None:
                raise ValueError("Unsupported operator")
            return op_func(left, right)
        raise ValueError("Unsupported expression")
