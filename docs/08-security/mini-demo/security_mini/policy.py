"""Role-based access control using fnmatch action patterns."""

from __future__ import annotations

import fnmatch

from security_mini.config import ROLE_PERMISSIONS


def is_allowed(role: str, action: str) -> bool:
    """Return True if the role may perform the action."""
    patterns = ROLE_PERMISSIONS.get(role, [])
    return any(fnmatch.fnmatch(action, pat) for pat in patterns)


def list_allowed_actions(role: str) -> list[str]:
    """Return the raw permission list for a role (for introspection)."""
    return list(ROLE_PERMISSIONS.get(role, []))
