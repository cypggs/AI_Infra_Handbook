"""Deterministic mock generator standing in for a real Claude model."""

from __future__ import annotations

MODELS = {"claude-haiku-mini", "claude-sonnet-mini", "claude-opus-mini"}

RESPONSES = {
    "claude-haiku-mini": "RAG retrieves relevant context to ground generation.",
    "claude-sonnet-mini": "Retrieval-augmented generation grounds answers in evidence.",
    "claude-opus-mini": (
        "Retrieval-augmented generation (RAG) combines retrieval and generation "
        "to ground answers in external evidence, reducing hallucination."
    ),
}


def pick_model(name: str) -> str:
    if name in MODELS:
        return name
    if name.startswith("claude-"):
        return "claude-haiku-mini"
    raise ValueError(f"unsupported model: {name}")


def complete(model: str, prompt: str) -> str:
    return RESPONSES.get(model, RESPONSES["claude-haiku-mini"])
