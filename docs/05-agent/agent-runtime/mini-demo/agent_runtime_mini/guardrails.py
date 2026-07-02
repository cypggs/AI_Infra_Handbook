"""Guardrails: safety, limits, and human approval."""

from typing import Any


class GuardrailViolation(Exception):
    """Raised when a guardrail blocks execution."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class Guardrails:
    """Configurable runtime guardrails."""

    def __init__(
        self,
        max_tool_calls: int = 10,
        forbidden_keywords: list[str] | None = None,
        forbidden_paths: list[str] | None = None,
        allowed_paths: list[str] | None = None,
        always_approve: bool = False,
    ):
        self.max_tool_calls = max_tool_calls
        self.forbidden_keywords = [w.lower() for w in (forbidden_keywords or [])]
        self.forbidden_paths = forbidden_paths or []
        self.allowed_paths = allowed_paths or []
        self.always_approve = always_approve

    def check_input(self, task: str) -> None:
        text = task.lower()
        for keyword in self.forbidden_keywords:
            if keyword in text:
                raise GuardrailViolation(f"Forbidden keyword detected: {keyword}")

    def check_tool_call(self, tool_call: dict[str, Any], call_count: int) -> None:
        if call_count > self.max_tool_calls:
            raise GuardrailViolation(
                f"Max tool calls exceeded ({self.max_tool_calls})"
            )

        name = tool_call.get("function", {}).get("name", "")
        args = tool_call.get("function", {}).get("arguments", "")
        arg_text = str(args).lower()

        for keyword in self.forbidden_keywords:
            if keyword in arg_text:
                raise GuardrailViolation(
                    f"Forbidden keyword in tool arguments: {keyword}"
                )

        if name in {"read_file", "write_file"}:
            path = self._extract_path(args)
            for forbidden in self.forbidden_paths:
                if path.startswith(forbidden):
                    raise GuardrailViolation(f"Forbidden path: {path}")
            if self.allowed_paths and not any(
                path.startswith(allowed) for allowed in self.allowed_paths
            ):
                raise GuardrailViolation(f"Path not in allow-list: {path}")

    def request_approval(self, tool_call: dict[str, Any]) -> bool:
        name = tool_call.get("function", {}).get("name", "")
        if name != "write_file":
            return True
        if self.always_approve:
            return True
        # Minimal interactive HITL placeholder.
        prompt = (
            f"Approve write_file({tool_call['function']['arguments']})? [y/N]: "
        )
        answer = input(prompt).strip().lower()
        return answer in {"y", "yes"}

    @staticmethod
    def _extract_path(arguments: Any) -> str:
        import json

        if isinstance(arguments, dict):
            return arguments.get("path", "")
        try:
            parsed = json.loads(arguments)
            return parsed.get("path", "")
        except Exception:
            return ""
