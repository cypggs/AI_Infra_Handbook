"""Entry point that exercises the agent runtime mini demo."""

from .guardrails import Guardrails
from .llm_client import MockLLMClient
from .observer import TraceObserver
from .runtime import AgentRuntime
from .tool_registry import default_tool_registry


def run_demo() -> None:
    """Run three illustrative tasks through the runtime."""
    tools = default_tool_registry()
    guardrails = Guardrails(
        max_tool_calls=5,
        forbidden_keywords=["secret", "password"],
        forbidden_paths=["/etc"],
        allowed_paths=["/tmp", "/home"],
        always_approve=True,
    )

    tasks = [
        ("math", "Calculate 25*4+10"),
        ("search", "Search for the current president of the United States"),
        ("blocked", "Write a secret to /etc/passwd"),
    ]

    for session_id, task in tasks:
        runtime = AgentRuntime(
            llm_client=MockLLMClient(),
            tools=tools,
            guardrails=guardrails,
            observer=TraceObserver(),
        )
        answer, observer = runtime.run(task, session_id=session_id)

        print(f"\n{'=' * 60}")
        print(f"Session : {session_id}")
        print(f"Task    : {task}")
        print(f"Answer  : {answer}")
        print(observer.render())

    print(f"\n{'=' * 60}")
    print("Demo complete.")


if __name__ == "__main__":
    run_demo()
