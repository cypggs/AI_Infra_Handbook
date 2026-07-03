"""Append-only audit logger for security decisions."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    timestamp: float
    principal: str
    role: str
    action: str
    resource: str
    decision: str
    reason: str


class AuditLogger:
    """Append-only JSONL audit log.

    Production systems should ship these events to a SIEM or immutable store
    (e.g., S3 with Object Lock, CloudTrail, Auditd) and protect local files.
    """

    def __init__(self, log_path: str | Path) -> None:
        self._path = Path(log_path)
        self._lock = threading.Lock()
        # Ensure parent directory exists.
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AuditEvent) -> None:
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def read_events(self) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        if not self._path.exists():
            return events
        with self._lock:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                events.append(AuditEvent(**data))
        return events

    def clear(self) -> None:
        with self._lock:
            if self._path.exists():
                self._path.unlink()
