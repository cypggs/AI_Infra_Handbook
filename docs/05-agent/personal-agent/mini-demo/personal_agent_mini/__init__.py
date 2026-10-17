"""Mini proactive personal AI agent (CPU-runnable, zero external deps).

Modules:
- clock: FakeClock for deterministic time control.
- memory: PersonalMemory (episode store + user profile + retrieval).
- connectors: fake personal data sources (email / calendar / files).
- agent: PersonalAgent proactive loop with a permission gate.
- demo: end-to-end scenarios.
"""

from .clock import FakeClock
from .memory import Episode, PersonalMemory, ProfileFact
from .connectors import CalendarConnector, EmailConnector, FilesConnector, SourceEvent
from .agent import Notification, PermissionGate, PersonalAgent, RelevanceScorer

__all__ = [
    "FakeClock",
    "Episode",
    "PersonalMemory",
    "ProfileFact",
    "CalendarConnector",
    "EmailConnector",
    "FilesConnector",
    "SourceEvent",
    "Notification",
    "PermissionGate",
    "PersonalAgent",
    "RelevanceScorer",
]
