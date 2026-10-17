from personal_agent_mini.clock import FakeClock
from personal_agent_mini.connectors import CalendarConnector, EmailConnector, FilesConnector


def test_event_ids_start_at_one_per_connector():
    clock = FakeClock()
    email = EmailConnector(clock)
    files = FilesConnector(clock)
    e1 = email.receive("a@b.c", "s", "b")
    e2 = email.receive("c@d.e", "s2", "b2")
    e3 = files.add_file("x.txt", "hello")
    assert [e.id for e in (e1, e2)] == ["evt1", "evt2"]
    assert e3.id == "evt1"  # each connector has its own sequence


def test_email_poll_returns_each_event_once():
    clock = FakeClock()
    email = EmailConnector(clock, inbox=[("a@b.c", "一", "x"), ("d@e.f", "二", "y")])
    first = email.poll()
    assert [e.payload["subject"] for e in first] == ["一", "二"]
    assert email.poll() == []


def test_email_send_records_outbox():
    clock = FakeClock()
    email = EmailConnector(clock)
    email.send("to@x.com", "主题", "正文")
    assert email.sent[0]["to"] == "to@x.com"


def test_calendar_add_event_emits_event():
    clock = FakeClock()
    cal = CalendarConnector(clock)
    ev = cal.add_event("周会", "2026-10-19T10:00:00", "2026-10-19T11:00:00")
    assert ev["id"] == "cal1"
    polled = cal.poll()
    assert polled[0].kind == "event_added"
    assert polled[0].payload["title"] == "周会"


def test_calendar_conflict_detection():
    clock = FakeClock()
    cal = CalendarConnector(clock, events=[
        ("A", "2026-10-19T14:00:00", "2026-10-19T15:00:00"),
        ("B", "2026-10-19T14:30:00", "2026-10-19T15:15:00"),
    ])
    conflicts = cal.conflicts()
    assert len(conflicts) == 1
    a, b = conflicts[0]
    assert {a["title"], b["title"]} == {"A", "B"}


def test_calendar_adjacent_events_are_not_conflicts():
    clock = FakeClock()
    cal = CalendarConnector(clock, events=[
        ("A", "2026-10-19T14:00:00", "2026-10-19T15:00:00"),
        ("B", "2026-10-19T15:00:00", "2026-10-19T16:00:00"),
    ])
    assert cal.conflicts() == []


def test_files_read_and_list():
    clock = FakeClock()
    files = FilesConnector(clock, {"b.txt": "2", "a.txt": "1"})
    files.add_file("c.txt", "3")
    assert files.read("a.txt") == "1"
    assert files.list_files() == ["a.txt", "b.txt", "c.txt"]
    kinds = [e.kind for e in files.poll()]
    assert kinds == ["file_added"]
