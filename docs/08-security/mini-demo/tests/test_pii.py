from security_mini.pii import PIIRedactor


def test_redact_email():
    r = PIIRedactor()
    assert r.redact("Contact alice@example.com") == "Contact [REDACTED]"


def test_redact_phone():
    r = PIIRedactor()
    assert r.redact("Call 555-123-4567") == "Call [REDACTED]"


def test_redact_ssn():
    r = PIIRedactor()
    assert r.redact("SSN 123-45-6789") == "SSN [REDACTED]"


def test_detect_multiple():
    r = PIIRedactor()
    found = r.detect("Reach alice@example.com or 555-123-4567")
    assert "email" in found
    assert "phone" in found


def test_no_pii_unchanged():
    r = PIIRedactor()
    text = "The weather is sunny."
    assert r.redact(text) == text
