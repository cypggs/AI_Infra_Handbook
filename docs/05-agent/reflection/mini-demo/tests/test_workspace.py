"""Tests for the scoped workspace."""

import pytest

from reflection_mini.workspace import Workspace


def test_read_write_shared():
    ws = Workspace()
    ws.write("draft_v0", "first draft")
    assert ws.read("draft_v0") == "first draft"
    assert ws.scope("draft_v0") == "shared"


def test_write_updates_history():
    ws = Workspace()
    ws.write("key", "a")
    ws.write("key", "b")
    assert ws.read("key") == "b"
    assert ws.history("key") == ["a", "b"]


def test_delete_removes_key():
    ws = Workspace()
    ws.write("key", "value")
    ws.delete("key")
    assert "key" not in ws.keys()
    with pytest.raises(KeyError):
        ws.read("key")


def test_read_missing_key_raises():
    ws = Workspace()
    with pytest.raises(KeyError):
        ws.read("missing")


def test_invalid_scope_raises():
    ws = Workspace()
    with pytest.raises(ValueError):
        ws.write("key", "value", scope="secret")


def test_readonly_cannot_be_overwritten():
    ws = Workspace()
    ws.write("config", "value", scope="readonly")
    with pytest.raises(ValueError):
        ws.write("config", "new value")


def test_private_scope_stored():
    ws = Workspace()
    ws.write("secret", "value", scope="private")
    assert ws.scope("secret") == "private"
    assert ws.read("secret") == "value"


def test_to_dict_snapshot():
    ws = Workspace()
    ws.write("a", 1)
    ws.write("b", 2)
    assert ws.to_dict() == {"a": 1, "b": 2}


def test_keys_returns_all_keys():
    ws = Workspace()
    ws.write("x", 1)
    ws.write("y", 2)
    assert sorted(ws.keys()) == ["x", "y"]
