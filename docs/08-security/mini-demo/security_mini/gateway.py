"""Security gateway orchestrating auth, authorization, guardrails, and audit."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from security_mini.auth import Principal, authenticate
from security_mini.policy import is_allowed
from security_mini.guardrails import GuardResult, PromptGuard
from security_mini.pii import PIIRedactor
from security_mini.audit import AuditEvent, AuditLogger


@dataclass(frozen=True)
class GatewayResponse:
    allowed: bool
    principal: str
    role: str
    decision: str
    reason: str
    response: str


class SecureGateway:
    """A minimal security gateway for AI requests.

    Pipeline:
        authenticate -> authorize -> input guard -> simulate llm -> output redaction -> audit -> return
    """

    def __init__(
        self,
        prompt_guard: PromptGuard | None = None,
        redactor: PIIRedactor | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self._guard = prompt_guard or PromptGuard()
        self._redactor = redactor or PIIRedactor()
        self._audit = audit_logger or AuditLogger("audit.log")

    def handle(self, request: dict[str, Any]) -> GatewayResponse:
        api_key = request.get("api_key", "")
        action = request.get("action", "")
        resource = request.get("resource", "")
        prompt = request.get("prompt", "")

        principal = authenticate(api_key)
        if principal is None:
            return self._finish(
                allowed=False,
                principal="anonymous",
                role="none",
                action=action,
                resource=resource,
                decision="deny",
                reason="invalid api key",
                response="",
            )

        if not is_allowed(principal.role, action):
            return self._finish(
                allowed=False,
                principal=principal.name,
                role=principal.role,
                action=action,
                resource=resource,
                decision="deny",
                reason=f"role '{principal.role}' not allowed for action '{action}'",
                response="",
            )

        guard_result = self._guard.check(prompt)
        if not guard_result.allowed:
            return self._finish(
                allowed=False,
                principal=principal.name,
                role=principal.role,
                action=action,
                resource=resource,
                decision="block",
                reason=guard_result.reason,
                response="",
            )

        raw_response = self._simulate_llm(prompt)
        safe_response = self._redactor.redact(raw_response)

        return self._finish(
            allowed=True,
            principal=principal.name,
            role=principal.role,
            action=action,
            resource=resource,
            decision="allow",
            reason="request processed",
            response=safe_response,
        )

    def _finish(
        self,
        allowed: bool,
        principal: str,
        role: str,
        action: str,
        resource: str,
        decision: str,
        reason: str,
        response: str,
    ) -> GatewayResponse:
        event = AuditEvent(
            timestamp=time.time(),
            principal=principal,
            role=role,
            action=action,
            resource=resource,
            decision=decision,
            reason=reason,
        )
        self._audit.log(event)
        return GatewayResponse(
            allowed=allowed,
            principal=principal,
            role=role,
            decision=decision,
            reason=reason,
            response=response,
        )

    @staticmethod
    def _simulate_llm(prompt: str) -> str:
        """Return a deterministic mock response for demo purposes."""
        lowered = prompt.lower()
        if "weather" in lowered:
            return "The weather in Beijing is sunny, 28°C. Contact bob@example.com for details."
        if "code" in lowered:
            return "Here is a Python snippet: print('hello')."
        return f"Acknowledged: '{prompt}'. For support call 555-123-4567."
