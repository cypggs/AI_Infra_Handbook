from __future__ import annotations

from typing import Dict, List


class WorkingMemory:
    """Holds the current session messages with optional budget truncation."""

    def __init__(self, budget: int = 500, budget_mode: str = "char"):
        if budget_mode not in ("char", "word"):
            raise ValueError("budget_mode must be 'char' or 'word'")
        self.budget = budget
        self.budget_mode = budget_mode
        self.messages: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the current session."""
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> List[Dict[str, str]]:
        """Return a shallow copy of the message list."""
        return list(self.messages)

    def clear(self) -> None:
        """Drop all messages."""
        self.messages.clear()

    def _measure(self, content: str) -> int:
        if self.budget_mode == "word":
            return len(content.split())
        return len(content)

    def truncate_to_budget(
        self, budget: int | None = None, preserve_system: bool = True
    ) -> None:
        """Trim messages until they fit ``budget``.

        When ``preserve_system`` is ``True``, system messages are kept at the
        front and truncation starts with the oldest non-system messages.
        """
        if budget is None:
            budget = self.budget

        if preserve_system:
            system = [m for m in self.messages if m["role"] == "system"]
            others = [m for m in self.messages if m["role"] != "system"]
            kept: List[Dict[str, str]] = list(system)
            used = sum(self._measure(m["content"]) for m in kept)
            for message in others:
                cost = self._measure(message["content"])
                if used + cost > budget:
                    break
                kept.append(message)
                used += cost
            self.messages = kept
        else:
            kept: List[Dict[str, str]] = []
            used = 0
            for message in self.messages:
                cost = self._measure(message["content"])
                if used + cost > budget and kept:
                    break
                kept.append(message)
                used += cost
            self.messages = kept
