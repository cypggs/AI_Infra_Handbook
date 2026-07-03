"""Simple regex-based PII detection and redaction."""

from __future__ import annotations

import re

from security_mini.config import PII_PATTERNS


class PIIRedactor:
    """Redact common PII patterns from text.

    Real systems use tools like Microsoft Presidio, AWS Macie, or Azure PII
    and often combine regex with named-entity recognition.
    """

    REDACTION_TOKEN = "[REDACTED]"

    def __init__(self, patterns: dict[str, str] | None = None) -> None:
        self._patterns = {name: re.compile(pat) for name, pat in (patterns or PII_PATTERNS).items()}

    def redact(self, text: str) -> str:
        for compiled in self._patterns.values():
            text = compiled.sub(self.REDACTION_TOKEN, text)
        return text

    def detect(self, text: str) -> dict[str, list[str]]:
        return {
            name: compiled.findall(text)
            for name, compiled in self._patterns.items()
            if compiled.search(text)
        }
