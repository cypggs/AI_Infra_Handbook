from __future__ import annotations

from typing import Dict, Optional, Tuple


class AuthMiddleware:
    """Validate a Bearer token and map it to a tenant."""

    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        self.api_keys = api_keys or {
            "sk-demo-123": "tenant-A",
            "sk-demo-456": "tenant-B",
        }

    def validate(self, auth_header: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        if not auth_header:
            return None, "Missing authorization header"

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None, "Invalid authorization header format"

        tenant = self.api_keys.get(parts[1])
        if tenant is None:
            return None, "Invalid API key"
        return tenant, None
