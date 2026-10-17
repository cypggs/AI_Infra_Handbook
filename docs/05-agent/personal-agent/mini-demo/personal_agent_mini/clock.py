"""Fake clock for deterministic demos and tests."""
from __future__ import annotations

from datetime import datetime, timedelta


class FakeClock:
    """A manually advanced clock; production agents read wall time instead."""

    def __init__(self, start: str = "2026-10-17T08:00:00"):
        self._now = datetime.fromisoformat(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, minutes: int = 0, hours: int = 0, days: int = 0) -> datetime:
        self._now += timedelta(minutes=minutes, hours=hours, days=days)
        return self._now

    def day(self) -> str:
        return self._now.date().isoformat()
