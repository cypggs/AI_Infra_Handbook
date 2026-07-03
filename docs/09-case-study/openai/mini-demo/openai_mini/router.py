"""Model routing logic."""

from __future__ import annotations

MODELS = {"gpt-mini", "gpt-large"}
DEFAULT_MODEL = "gpt-mini"


def pick_model(requested: str) -> str:
    """Return a concrete model name or raise ValueError."""
    if requested in MODELS:
        return requested
    if requested.startswith("gpt-"):
        return DEFAULT_MODEL
    raise ValueError(f"unsupported model: {requested}")


def list_models() -> list[dict[str, str]]:
    return [{"id": m, "object": "model", "owned_by": "openai-mini"} for m in sorted(MODELS)]
