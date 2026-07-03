"""Lightweight input/output guardrails for the demo."""

from __future__ import annotations

import re
from dataclasses import dataclass

from security_mini.config import INJECTION_PATTERNS


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str = ""


class PromptGuard:
    """Simple regex-based prompt injection detector.

    Production systems should combine this with:
    - Dedicated classifiers (e.g., Llama Guard, OpenAI Moderation)
    - LLM-as-judge evaluations
    - Per-tool schema validation
    """

    def __init__(self, patterns: list[str] | None = None) -> None:
        self._patterns = [re.compile(p, re.IGNORECASE) for p in (patterns or INJECTION_PATTERNS)]

    def check(self, prompt: str) -> GuardResult:
        for pattern in self._patterns:
            if pattern.search(prompt):
                return GuardResult(
                    allowed=False,
                    reason=f"blocked by prompt guard: matched pattern '{pattern.pattern}'",
                )
        return GuardResult(allowed=True, reason="input accepted")
