"""Working memory with token-budget truncation and deterministic compaction."""

from typing import Any, Callable


def _default_summarizer(messages: list[dict[str, Any]]) -> str:
    """Deterministic placeholder summarizer: keep roles and first words."""
    parts = [f"{m['role']}: {str(m.get('content', ''))[:20]}" for m in messages]
    return "[compacted " + str(len(messages)) + " messages] " + " | ".join(parts[:3])


class WorkingMemory:
    """Maintains conversation history for a session."""

    def __init__(
        self,
        max_tokens: int = 500,
        summarizer: Callable[[list[dict[str, Any]]], str] | None = None,
    ):
        self.messages: list[dict[str, Any]] = []
        self.max_tokens = max_tokens
        self.summarizer = summarizer or _default_summarizer
        self.compaction_count = 0

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

    def compact(self, keep_recent: int = 2) -> dict[str, Any]:
        """Summarize oldest non-system messages into one compaction message.

        Mirrors production harnesses (2026): compaction is a first-class
        loop stage, not an afterthought. Deterministic given the same
        messages and summarizer. Returns a stats dict for observability.
        """
        system = [m for m in self.messages if m["role"] == "system"]
        rest = [m for m in self.messages if m["role"] != "system"]
        if len(rest) <= keep_recent:
            return {"compacted": 0, "remaining": len(self.messages)}
        head, tail = rest[:-keep_recent], rest[-keep_recent:]
        summary = self.summarizer(head)
        self.messages = system + [
            {"role": "user", "content": summary, "compacted": True}
        ] + tail
        self.compaction_count += 1
        return {"compacted": len(head), "remaining": len(self.messages)}

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
