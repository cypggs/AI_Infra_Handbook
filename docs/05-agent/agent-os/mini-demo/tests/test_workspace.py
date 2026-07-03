"""Tests for the shared and per-process workspace."""

from agent_os_mini.workspace import Workspace


def test_workspace_shared_read_write():
    ws = Workspace()
    ws.write_shared("x", 42)

    assert ws.read_shared("x") == 42
    assert ws.read_shared("missing", "default") == "default"


def test_workspace_private_read_write():
    ws = Workspace()
    ws.write_private("p1", "temp", 7)

    assert ws.read_private("p1", "temp") == 7
    assert ws.read_private("p1", "missing") is None


def test_workspace_snapshots_are_copies():
    ws = Workspace()
    ws.write_shared("x", 1)
    ws.write_private("p1", "y", 2)

    shared = ws.shared_snapshot()
    private = ws.private_snapshot("p1")
    shared["x"] = 999
    private["y"] = 999

    assert ws.read_shared("x") == 1
    assert ws.read_private("p1", "y") == 2


def test_workspace_clear():
    ws = Workspace()
    ws.write_shared("x", 1)
    ws.write_private("p1", "y", 2)
    ws.clear()

    assert ws.read_shared("x") is None
    assert ws.read_private("p1", "y") is None
