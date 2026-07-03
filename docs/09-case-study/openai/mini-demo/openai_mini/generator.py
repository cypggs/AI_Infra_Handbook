"""Deterministic mock text generator."""

from __future__ import annotations


RESPONSES = {
    "gpt-mini": "Hello! This is gpt-mini. How can I help?",
    "gpt-large": "Greetings from gpt-large. I can provide more detailed answers.",
}


def generate(model: str, prompt: str) -> list[str]:
    """Return a list of tokens (words) for streaming."""
    text = RESPONSES.get(model, RESPONSES["gpt-mini"])
    # Append a hint about the prompt to make it feel dynamic.
    text += f" (prompt: '{prompt}')"
    return text.split()


def complete(model: str, prompt: str) -> str:
    return " ".join(generate(model, prompt))
