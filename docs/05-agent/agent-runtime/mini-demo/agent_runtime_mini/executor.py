"""Tool executor with timeout and exception isolation."""

import threading
import time
from typing import Any

from .tool_registry import ToolRegistry


class ToolExecutionError(Exception):
    """Wraps any problem that occurs while running a tool."""

    def __init__(self, message: str, original: Exception | None = None):
        self.original = original
        super().__init__(message)


class ToolExecutor:
    """Runs a tool call in an isolated thread with a timeout."""

    def __init__(self, registry: ToolRegistry, timeout: float = 5.0):
        self.registry = registry
        self.timeout = timeout

    def execute(
        self,
        tool_call: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        result_container: dict[str, Any] = {}
        exception_container: dict[str, Exception] = {}

        def _target() -> None:
            try:
                result_container["result"] = self.registry.dispatch(
                    tool_call, context=context
                )
            except Exception as exc:  # pylint: disable=broad-except
                exception_container["exc"] = exc

        thread = threading.Thread(target=_target, daemon=True)
        start = time.monotonic()
        thread.start()
        thread.join(timeout=self.timeout)
        elapsed = time.monotonic() - start

        if thread.is_alive():
            raise ToolExecutionError(
                f"Tool call timed out after {self.timeout}s"
            )

        if "exc" in exception_container:
            original = exception_container["exc"]
            raise ToolExecutionError(
                f"Tool failed: {type(original).__name__}: {original}"
            ) from original

        return result_container["result"]

    def __repr__(self) -> str:  # pragma: no cover
        return f"ToolExecutor(timeout={self.timeout})"
