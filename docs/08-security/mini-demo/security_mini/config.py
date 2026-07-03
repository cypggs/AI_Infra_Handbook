"""Sample configuration for the security gateway demo.

In production these values would live in a secret manager, policy database,
and configuration store. They are hard-coded here only for a self-contained demo.
"""

from __future__ import annotations

# action identifiers used by the policy engine
ACTION_CHAT = "llm:chat"
ACTION_ADMIN = "llm:admin"
ACTION_RAG_SEARCH = "rag:search"

# demo API keys mapped to principal metadata
API_KEYS: dict[str, dict[str, str]] = {
    "dev-sk-12345": {"name": "developer-alice", "role": "developer"},
    "admin-sk-99999": {"name": "admin-bob", "role": "admin"},
    "readonly-sk-00000": {"name": "reader-carol", "role": "readonly"},
}

# role -> list of allowed action patterns (fnmatch syntax)
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["*"],
    "developer": ["llm:chat", "rag:search"],
    "readonly": ["llm:chat"],
}

# Simple prompt-injection / jailbreak indicators (demo only).
# Production systems use dedicated classifiers, LLM-as-judge, or ensemble models.
INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(previous|all)\s+instructions",
    r"ignore\s+the\s+above",
    r"system\s+prompt",
    r"you\s+are\s+now\s+",
    r"DAN",
    r"do\s+anything\s+now",
    r"reveal\s+your\s+(instructions|prompt|system)",
    r"forget\s+(everything|your\s+instructions)",
]

# PII patterns used for detection/redaction (demo only).
PII_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
}
