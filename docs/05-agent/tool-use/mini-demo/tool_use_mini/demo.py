"""End-to-end demo of the tool-use loop."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from tool_use_mini.executor import Executor, ToolResult
from tool_use_mini.formatter import format_results, format_tool_message
from tool_use_mini.llm_client import MockLLMClient
from tool_use_mini.parser import ToolCall, parse_tool_calls
from tool_use_mini.policy import Policy
from tool_use_mini.tool import build_default_registry, reset_exchange_rate_service
from tool_use_mini.validator import ValidationError, validate_arguments


USER_QUESTION = "帮我查一下北京天气和美元兑人民币汇率，然后计算 1000 美元能换多少人民币。"


def _validate_calls(tool_calls: List[ToolCall], registry) -> tuple[List[ToolCall], List[ToolResult]]:
    """Validate tool calls against their schemas.

    Returns the calls that passed validation plus synthetic error results for
    any calls that failed.
    """
    valid_calls: List[ToolCall] = []
    error_results: List[ToolResult] = []
    for call in tool_calls:
        try:
            tool = registry.get(call.name)
        except KeyError as exc:
            error_results.append(
                ToolResult(
                    call_id=call.id,
                    name=call.name,
                    arguments=call.arguments,
                    success=False,
                    error=str(exc),
                )
            )
            continue

        errors = validate_arguments(call.arguments, tool.parameters)
        if errors:
            messages = [f"{e.path}: {e.message}" for e in errors]
            error_results.append(
                ToolResult(
                    call_id=call.id,
                    name=call.name,
                    arguments=call.arguments,
                    success=False,
                    error="Validation failed: " + "; ".join(messages),
                )
            )
            continue

        valid_calls.append(call)

    return valid_calls, error_results


def _print_trace(messages: List[Dict[str, Any]]) -> None:
    """Pretty-print the conversation and tool-use trace."""
    print("=" * 60)
    print("Tool Use Mini Demo - Full Trace")
    print("=" * 60)
    for message in messages:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        print(f"\n[{role}]")
        if content:
            print(f"  content: {content}")
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", tc)
                name = fn.get("name", tc.get("name", "unknown"))
                args = fn.get("arguments", tc.get("arguments", "{}"))
                print(f"  tool_call: {name}({args})")
        if "tool_call_id" in message:
            print(f"  tool_call_id: {message['tool_call_id']}")
            print(f"  result: {content}")
    print("\n" + "=" * 60)


def run_demo() -> str:
    """Run the full tool-use demo and return the final answer.

    The demo exercises:
    - parallel tool calls (weather + exchange rate)
    - a tool-level error with fallback data (exchange rate first call)
    - validation failure and retry (malformed calculate_rmb)
    - final natural-language answer
    """
    reset_exchange_rate_service()

    registry = build_default_registry()
    executor = Executor(registry, default_timeout=10.0, default_max_retries=1)
    policy = Policy(
        allowed_tools={"get_weather", "get_exchange_rate", "calculate_rmb"},
        max_calls=10,
        timeout_budget_seconds=60.0,
    )
    client = MockLLMClient()

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": USER_QUESTION},
    ]

    final_answer = ""

    while policy.call_count < policy.max_calls:
        response = client.chat(messages)
        messages.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls,
            }
        )

        if not response.tool_calls:
            final_answer = response.content
            break

        tool_calls, parse_errors = parse_tool_calls(response.tool_calls)

        # Turn parse errors into synthetic tool results so the model can retry.
        synthetic_errors: List[ToolResult] = [
            ToolResult(
                call_id=f"parse_error_{e.index}",
                name="unknown",
                arguments={},
                success=False,
                error=f"Parse error at index {e.index}: {e.reason}",
            )
            for e in parse_errors
        ]

        valid_calls, validation_errors = _validate_calls(tool_calls, registry)

        # Enforce policy and execute valid calls in parallel.
        for call in valid_calls:
            policy.check(call.name)

        results = executor.execute(valid_calls)
        results.extend(validation_errors)
        results.extend(synthetic_errors)

        # Append all results to the conversation.
        for result in results:
            messages.append(format_tool_message(result))

        # If every result is an error, continue to let the model retry.
        if results and all(not r.success for r in results):
            continue

    _print_trace(messages)
    print(f"Final answer:\n{final_answer}\n")
    return final_answer


if __name__ == "__main__":
    run_demo()
