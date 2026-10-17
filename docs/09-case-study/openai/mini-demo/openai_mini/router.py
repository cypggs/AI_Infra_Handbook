"""Model routing logic."""

from __future__ import annotations

MODELS = {"gpt-mini", "gpt-large"}
DEFAULT_MODEL = "gpt-mini"

# Capability-tier aliases mirroring OpenAI's Sol/Terra/Luna-style product tiers:
# a budget tier maps to the small backend, mid/flagship tiers to the large one.
TIER_ALIASES = {
    "gpt-6-luna": "gpt-mini",
    "gpt-6-sol": "gpt-large",
    "gpt-6-astra": "gpt-large",
}

VALID_EFFORTS = {"low", "medium", "high"}


def pick_model(requested: str, effort: str = "medium") -> str:
    """Return a concrete model name or raise ValueError.

    Mirrors OpenAI's system-level routing: unknown ``gpt-*`` names fall back
    to a default, but a high ``reasoning_effort`` upgrades the request to the
    more capable backend (like GPT-5/GPT-6 routing simple prompts to the
    instant model and hard ones to the thinking model).
    """
    if requested in MODELS:
        return requested
    if requested in TIER_ALIASES:
        return TIER_ALIASES[requested]
    if requested.startswith("gpt-"):
        if effort == "high":
            return "gpt-large"
        return DEFAULT_MODEL
    raise ValueError(f"unsupported model: {requested}")


def list_models() -> list[dict[str, str]]:
    return [{"id": m, "object": "model", "owned_by": "openai-mini"} for m in sorted(MODELS)]
