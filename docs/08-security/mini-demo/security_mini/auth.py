"""Authentication primitives with constant-time key comparison."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from security_mini.config import API_KEYS


@dataclass(frozen=True)
class Principal:
    name: str
    role: str
    api_key_id: str


def authenticate(api_key: str) -> Principal | None:
    """Return the principal for a valid API key, otherwise None.

    Uses hmac.compare_digest to avoid timing side-channels.
    """
    for key_id, meta in API_KEYS.items():
        if hmac.compare_digest(api_key, key_id):
            return Principal(
                name=meta["name"],
                role=meta["role"],
                api_key_id=key_id,
            )
    return None
