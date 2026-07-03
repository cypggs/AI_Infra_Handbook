from security_mini.auth import authenticate


def test_valid_key_returns_principal():
    principal = authenticate("dev-sk-12345")
    assert principal is not None
    assert principal.name == "developer-alice"
    assert principal.role == "developer"


def test_invalid_key_returns_none():
    assert authenticate("not-a-key") is None


def test_partial_key_does_not_match():
    # Constant-time comparison should not leak prefix information.
    assert authenticate("dev-sk-1234") is None
    assert authenticate("dev-sk-123456") is None
