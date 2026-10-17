"""Per-process context buffer: token budget and deterministic compaction.

Context engineering as a first-class OS resource: every agent process owns a
private context buffer (the analogue of a process address space). Writes are
subject to a token budget enforced by the kernel-side buffer, and overflow
triggers deterministic compaction that keeps the oldest and newest entries
while dropping the earliest ones in between.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ContextOverflow(Exception):
    """Raised when a single entry cannot fit into the context budget."""


@dataclass(frozen=True)
class ContextEntry:
    """One immutable entry in a process context buffer."""

    seq: int
    content: str
    tokens: int
    compacted: bool = False


class ContextBuffer:
    """A per-process token-budgeted context with deterministic compaction.

    Args:
        max_tokens: hard token budget for this buffer.
        reserve_ratio: fraction of the budget protected as "recent" tail
            entries during compaction (the rest is protected as "old" head).

    Determinism: token counts are provided by the caller, never estimated,
    so every operation is fully reproducible.
    """

    def __init__(self, max_tokens: int = 64, reserve_ratio: float = 0.5) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if not 0.0 < reserve_ratio < 1.0:
            raise ValueError("reserve_ratio must be in (0, 1)")
        self.max_tokens = max_tokens
        self.reserve_ratio = reserve_ratio
        self._entries: list[ContextEntry] = []
        self._seq = 0
        self.compactions = 0

    @property
    def token_count(self) -> int:
        """Current total token usage."""
        return sum(entry.tokens for entry in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def append(self, content: str, tokens: int = 1) -> ContextEntry:
        """Append an entry, enforcing the hard token budget.

        If the budget is exceeded, compaction runs first; if a single entry
        still cannot fit, ContextOverflow is raised (hard quota, like an OS
        refusing an allocation that can never succeed).
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self.max_tokens:
            raise ContextOverflow(
                f"entry of {tokens} tokens exceeds budget {self.max_tokens}"
            )
        while self.token_count + tokens > self.max_tokens and len(self._entries) > 1:
            if self.compact(required_tokens=tokens) == 0:
                break
        if self.token_count + tokens > self.max_tokens:
            raise ContextOverflow("context budget exhausted")
        self._seq += 1
        entry = ContextEntry(seq=self._seq, content=content, tokens=tokens)
        self._entries.append(entry)
        return entry

    def compact(self, required_tokens: int = 0) -> int:
        """Drop the earliest non-protected entries; return dropped token count.

        Compacts until usage fits ``max_tokens - required_tokens`` so an
        in-flight append has room after compaction. Keeps the oldest entries
        whose token sum fits the head reserve and the newest entries whose
        token sum fits the tail reserve, so both early instructions and
        recent state survive.
        """
        target = self.max_tokens - max(required_tokens, 0)
        total = self.token_count
        if total <= target:
            return 0
        tail_budget = int(target * self.reserve_ratio)
        # Leave one token for the compaction marker so post-compaction usage
        # is guaranteed to fit back within target.
        head_budget = target - 1 - tail_budget
        if head_budget < 0:
            head_budget = 0

        head: list[ContextEntry] = []
        head_tokens = 0
        idx = 0
        while idx < len(self._entries):
            entry = self._entries[idx]
            if head_tokens + entry.tokens > head_budget:
                break
            head.append(entry)
            head_tokens += entry.tokens
            idx += 1

        tail: list[ContextEntry] = []
        tail_tokens = 0
        j = len(self._entries) - 1
        while j >= idx:
            entry = self._entries[j]
            if tail_tokens + entry.tokens > tail_budget:
                break
            tail.append(entry)
            tail_tokens += entry.tokens
            j -= 1

        dropped = self._entries[idx : j + 1]
        if not dropped:
            return 0
        self.compactions += 1
        marker = ContextEntry(
            seq=head[-1].seq if head else 0,
            content=f"<compacted {len(dropped)} entries, {sum(e.tokens for e in dropped)} tokens>",
            tokens=1,
            compacted=True,
        )
        self._entries = head + [marker] + list(reversed(tail))
        return sum(entry.tokens for entry in dropped)

    def snapshot(self) -> list[str]:
        """Return entry contents in order (compaction markers included)."""
        return [entry.content for entry in self._entries]

    def __repr__(self) -> str:
        return (
            f"ContextBuffer(tokens={self.token_count}/{self.max_tokens}, "
            f"entries={len(self._entries)}, compactions={self.compactions})"
        )
