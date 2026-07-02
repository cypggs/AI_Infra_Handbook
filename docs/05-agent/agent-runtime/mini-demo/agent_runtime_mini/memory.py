"""Working memory with simple token-budget truncation."""

from typing import Any


class WorkingMemory:
    """Maintains conversation history for a session."""

    def __init__(self, max_tokens: int = 500):
        self.messages: list[dict[str, Any]] = []
        self.max_tokens = max_tokens

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        message = {"role": role, "content": content, **kwargs}
        self.messages.append(message)
        self._truncate()

    def add_system_prompt(self, content: str) -> None:
        self.add_message("system", content)

    def add_user_message(self, content: str) -> None:
        self.add_message("user", content)

    def add_assistant_message(self, content: str, tool_calls: list[dict[str, Any]] | None = None) -> None:
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.add_message(**message)

    def add_tool_message(self, tool_call_id: str, content: str) -> None:
        self.add_message(
            "tool",
            content,
            tool_call_id=tool_call_id,
        )

    def token_count(self) -> int:
        return sum(
            len(str(m.get("content", "")).split()) for m in self.messages
        )

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def _truncate(self) -> None:
        """Drop oldest non-system messages while over budget."""
        while (
            self.token_count() > self.max_tokens
            and len(self.messages) > 1
        ):
            for idx, message in enumerate(self.messages):
                if message["role"] != "system":
                    del self.messages[idx]
                    break
            else:
                break

    def __repr__(self) -> str:  # pragma: no cover
        return f"WorkingMemory(messages={len(self.messages)}, tokens={self.token_count()})"
