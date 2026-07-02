"""Tests for the Blackboard."""

from multi_agent_mini.blackboard import Blackboard


def test_read_write():
    board = Blackboard()
    board.write("facts", "some facts")
    assert board.read("facts") == "some facts"


def test_read_missing():
    board = Blackboard()
    assert board.read("missing") is None


def test_delete():
    board = Blackboard()
    board.write("x", 1)
    assert board.delete("x") is True
    assert board.read("x") is None
    assert board.delete("x") is False


def test_scopes_in_to_dict():
    board = Blackboard()
    board.write("shared_key", "visible", scope="shared")
    board.write("readonly_key", "visible", scope="readonly")
    board.write("private_key", "hidden", scope="private")

    snapshot = board.to_dict()
    assert "shared_key" in snapshot
    assert "readonly_key" in snapshot
    assert "private_key" not in snapshot


def test_invalid_scope_raises():
    board = Blackboard()
    try:
        board.write("k", "v", scope="secret")
    except ValueError as exc:
        assert "Invalid scope" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_keys_and_scope():
    board = Blackboard()
    board.write("a", 1, scope="shared")
    assert board.keys() == ["a"]
    assert board.scope("a") == "shared"
    assert board.scope("missing") is None
