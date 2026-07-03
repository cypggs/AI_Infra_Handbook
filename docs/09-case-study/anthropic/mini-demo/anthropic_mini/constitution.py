"""A deterministic, rule-based stand-in for the Constitutional AI SL phase.

The real Constitutional AI asks a model to *critique* its own response against a
set of principles and then *revise* it. Here we replace the model with simple
rules so the demo runs offline and is fully deterministic. The shape of the
loop -- ``critique -> revise`` against a versioned constitution -- is what
matters and what this file demonstrates.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principle:
    """One rule of the constitution.

    ``trigger`` is a substring whose presence violates the principle; ``fix`` is
    a ``(bad, good)`` replacement pair applied during revision.
    """

    name: str
    trigger: str
    critique: str
    fix: tuple[str, str]


# A tiny, illustrative "Claude constitution". The real one draws on sources such
# as the UN Declaration of Human Rights and platform terms of service.
CONSTITUTION: list[Principle] = [
    Principle(
        name="honest",
        trigger="100% sure",
        critique="claims unwarranted certainty, violating the honesty principle",
        fix=("100% sure", "it is possible that"),
    ),
    Principle(
        name="honest",
        trigger="definitely no risk",
        critique="downplays uncertainty, violating the honesty principle",
        fix=("definitely no risk", "there is some risk"),
    ),
    Principle(
        name="harmless",
        trigger="build a weapon",
        critique="provides potentially harmful instructions, violating the harmlessness principle",
        fix=("build a weapon", "I can't help with that"),
    ),
    Principle(
        name="harmless",
        trigger="real credit card number",
        critique="may surface sensitive data, violating the harmlessness principle",
        fix=("real credit card number", "a masked card number"),
    ),
]


def critique(response: str) -> list[str]:
    """Return one critique line per violated principle (empty if all clear)."""
    out: list[str] = []
    for p in CONSTITUTION:
        if p.trigger in response:
            out.append(f"[{p.name}] {p.critique}")
    return out


def revise(response: str) -> str:
    """Apply every principle's fix to the response."""
    for p in CONSTITUTION:
        response = response.replace(p.fix[0], p.fix[1])
    return response


def constitutional_revise(response: str) -> tuple[str, list[str]]:
    """The SL-phase loop: critique, then revise if any principle was violated."""
    problems = critique(response)
    revised = revise(response) if problems else response
    return revised, problems
