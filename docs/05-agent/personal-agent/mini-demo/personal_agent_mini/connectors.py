"""Fake personal data connectors: email / calendar / files.

Each connector mirrors the shape of a real personal-data connector
(OAuth-scoped, event-emitting) without any network or credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SourceEvent:
    id: str
    source: str  # email / calendar / files
    kind: str  # new_email / event_added / file_added
    ts: datetime
    payload: dict


class Connector:
    """Base class: holds an event log; poll() drains unseen events once."""

    name = "base"

    def __init__(self, clock) -> None:
        self.clock = clock
        self._events: list[SourceEvent] = []
        self._cursor = 0
        self._counter = 0

    def _emit(self, kind: str, payload: dict) -> SourceEvent:
        self._counter += 1
        ev = SourceEvent(f"evt{self._counter}", self.name, kind, self.clock.now(), payload)
        self._events.append(ev)
        return ev

    def poll(self) -> list[SourceEvent]:
        pending = self._events[self._cursor:]
        self._cursor = len(self._events)
        return list(pending)


class EmailConnector(Connector):
    """Inbox + outbox. receive() simulates an incoming message."""

    name = "email"

    def __init__(self, clock, inbox=()) -> None:
        super().__init__(clock)
        self.sent: list[dict] = []
        for sender, subject, body in inbox:
            self.receive(sender, subject, body)

    def receive(self, sender: str, subject: str, body: str) -> SourceEvent:
        return self._emit("new_email", {"from": sender, "subject": subject, "body": body})

    def send(self, to: str, subject: str, body: str) -> dict:
        record = {"to": to, "subject": subject, "body": body, "ts": self.clock.now()}
        self.sent.append(record)
        return record


class CalendarConnector(Connector):
    """Event list with overlap detection."""

    name = "calendar"

    def __init__(self, clock, events=()) -> None:
        super().__init__(clock)
        self._calendar: list[dict] = []
        for title, start, end in events:
            self.add_event(title, start, end)

    def add_event(self, title: str, start: str, end: str) -> dict:
        ev = {
            "id": f"cal{len(self._calendar) + 1}",
            "title": title,
            "start": datetime.fromisoformat(start),
            "end": datetime.fromisoformat(end),
        }
        self._calendar.append(ev)
        self._emit("event_added", {"title": title, "start": start, "end": end})
        return ev

    def events(self) -> list[dict]:
        return list(self._calendar)

    def conflicts(self) -> list[tuple[dict, dict]]:
        out: list[tuple[dict, dict]] = []
        evs = sorted(self._calendar, key=lambda e: e["start"])
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                a, b = evs[i], evs[j]
                if b["start"] < a["end"]:
                    out.append((a, b))
                else:
                    break
        return out


class FilesConnector(Connector):
    """Tiny key-value file system."""

    name = "files"

    def __init__(self, clock, files: dict | None = None) -> None:
        super().__init__(clock)
        self._files = dict(files or {})

    def add_file(self, name: str, content: str) -> SourceEvent:
        self._files[name] = content
        return self._emit("file_added", {"name": name})

    def read(self, name: str) -> str:
        return self._files[name]

    def list_files(self) -> list[str]:
        return sorted(self._files)
