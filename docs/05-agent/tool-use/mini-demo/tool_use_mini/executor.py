"""Execute parsed tool calls with parallel, timeout, retry, and fallback support."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from tool_use_mini.parser import ToolCall
from tool_use_mini.tool import ToolRegistry


@dataclass
class ToolResult:
    """Result of executing a single tool call."""

    call_id: str
    name: str
    arguments: Dict[str, Any]
    success: bool
    data: Any = None
    error: Optional[str] = None
    attempts: int = 1


def _execute_single(
    registry: ToolRegistry,
    tool_call: ToolCall,
    timeout: Optional[float],
    max_retries: int,
    fallback: Any,
) -> ToolResult:
    """Execute one tool call with optional timeout and retry."""
    last_error: Optional[str] = None
    attempts = 0

    for attempt in range(1, max_retries + 1):
        attempts = attempt
        try:
            # The tool registry may raise or return a result; timeouts are
            # enforced by wrapping the call in a future with a deadline.
            def _call() -> Any:
                return registry.call(tool_call.name, tool_call.arguments)

            if timeout is not None:
                import threading

                result_container: List[Any] = []
                exception_container: List[BaseException] = []

                def _target() -> None:
                    try:
                        result_container.append(_call())
                    except BaseException as exc:  # pragma: no cover - defensive
                        exception_container.append(exc)

                thread = threading.Thread(target=_target)
                thread.start()
                thread.join(timeout=timeout)
                if thread.is_alive():
                    # We cannot forcibly kill a thread; mark it timed out.
                    raise TimeoutError(f"tool call exceeded {timeout}s timeout")
                if exception_container:
                    raise exception_container[0]
                result = result_container[0]
            else:
                result = _call()

            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                arguments=tool_call.arguments,
                success=True,
                data=result,
                attempts=attempts,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < max_retries:
                continue
            break

    if fallback is not None:
        return ToolResult(
            call_id=tool_call.id,
            name=tool_call.name,
            arguments=tool_call.arguments,
            success=True,
            data=fallback,
            error=f"used fallback after {attempts} failed attempt(s): {last_error}",
            attempts=attempts,
        )

    return ToolResult(
        call_id=tool_call.id,
        name=tool_call.name,
        arguments=tool_call.arguments,
        success=False,
        error=last_error,
        attempts=attempts,
    )


class Executor:
    """Runs tool calls against a registry with parallelism and retry options."""

    def __init__(
        self,
        registry: ToolRegistry,
        default_timeout: Optional[float] = 10.0,
        default_max_retries: int = 1,
        default_fallback: Any = None,
    ) -> None:
        self.registry = registry
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries
        self.default_fallback = default_fallback

    def execute(
        self,
        tool_calls: List[ToolCall],
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        fallback: Any = None,
        max_workers: Optional[int] = None,
    ) -> List[ToolResult]:
        """Execute a list of tool calls in parallel.

        Parameters mirror the defaults set on the executor; passing ``None``
        keeps the executor default.
        """
        timeout = self.default_timeout if timeout is None else timeout
        retries = self.default_max_retries if max_retries is None else max_retries
        fallback = self.default_fallback if fallback is None else fallback

        if not tool_calls:
            return []

        results: List[ToolResult] = []
        with ThreadPoolExecutor(max_workers=max_workers or len(tool_calls)) as pool:
            future_to_call = {
                pool.submit(_execute_single, self.registry, call, timeout, retries, fallback): call
                for call in tool_calls
            }
            for future in as_completed(future_to_call):
                results.append(future.result())

        # Return in the same order as the input calls for deterministic output.
        order = {call.id: index for index, call in enumerate(tool_calls)}
        results.sort(key=lambda r: order.get(r.call_id, 0))
        return results

    def execute_one(
        self,
        tool_call: ToolCall,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        fallback: Any = None,
    ) -> ToolResult:
        """Execute a single tool call."""
        results = self.execute(
            [tool_call],
            timeout=timeout,
            max_retries=max_retries,
            fallback=fallback,
        )
        return results[0]
