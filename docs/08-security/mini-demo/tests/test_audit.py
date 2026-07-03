import tempfile

from security_mini.audit import AuditEvent, AuditLogger


def test_log_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = AuditLogger(f"{tmpdir}/audit.log")
        event = AuditEvent(
            timestamp=1.0,
            principal="alice",
            role="developer",
            action="llm:chat",
            resource="gpt-mini",
            decision="allow",
            reason="ok",
        )
        logger.log(event)
        events = logger.read_events()
        assert len(events) == 1
        assert events[0].principal == "alice"


def test_clear():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = AuditLogger(f"{tmpdir}/audit.log")
        logger.log(
            AuditEvent(
                timestamp=1.0,
                principal="alice",
                role="developer",
                action="llm:chat",
                resource="gpt-mini",
                decision="allow",
                reason="ok",
            )
        )
        logger.clear()
        assert logger.read_events() == []
