from personal_agent_mini.clock import FakeClock


def test_now_returns_start_time():
    clock = FakeClock("2026-10-17T08:00:00")
    assert clock.now().isoformat() == "2026-10-17T08:00:00"


def test_advance_minutes():
    clock = FakeClock("2026-10-17T08:00:00")
    clock.advance(minutes=90)
    assert clock.now().isoformat() == "2026-10-17T09:30:00"


def test_advance_hours_and_days_compose():
    clock = FakeClock("2026-10-17T08:00:00")
    clock.advance(hours=2, days=1)
    assert clock.now().isoformat() == "2026-10-18T10:00:00"


def test_day_format():
    clock = FakeClock("2026-10-17T23:59:00")
    assert clock.day() == "2026-10-17"
    clock.advance(minutes=2)
    assert clock.day() == "2026-10-18"
