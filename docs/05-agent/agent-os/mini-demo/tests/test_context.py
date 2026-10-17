"""Tests for the per-process context buffer (budget + compaction)."""

import pytest

from agent_os_mini import (
    AgentProcess,
    ContextBuffer,
    ContextEntry,
    ContextOverflow,
    MessageBus,
    Observer,
    ProcessState,
    Workspace,
)


def _make_process(context=None):
    return AgentProcess(
        pid="p1",
        role="worker",
        step_fn=lambda p: None,
        workspace=Workspace(),
        bus=MessageBus(),
        observer=Observer(),
        context=context,
    )


class TestContextBuffer:
    def test_append_within_budget(self):
        buf = ContextBuffer(max_tokens=8)
        buf.append("system prompt", tokens=3)
        buf.append("observation", tokens=2)
        assert buf.token_count == 5
        assert len(buf) == 2

    def test_append_tracks_monotonic_seq(self):
        buf = ContextBuffer(max_tokens=8)
        e1 = buf.append("a")
        e2 = buf.append("b")
        assert e2.seq == e1.seq + 1
        assert isinstance(e1, ContextEntry)

    def test_single_entry_exceeding_budget_raises(self):
        buf = ContextBuffer(max_tokens=4)
        with pytest.raises(ContextOverflow):
            buf.append("huge", tokens=5)
        assert len(buf) == 0

    def test_compaction_triggered_by_append_keeps_head_and_tail(self):
        buf = ContextBuffer(max_tokens=6, reserve_ratio=0.5)
        # head: 2 tokens, middle: 2, tail region: 2 -> appending one more
        # entry must compact the middle away.
        buf.append("instructions", tokens=2)
        buf.append("m1", tokens=1)
        buf.append("m2", tokens=1)
        buf.append("latest", tokens=2)
        entry = buf.append("new", tokens=1)  # forces compaction
        snap = buf.snapshot()
        assert snap[0] == "instructions"  # head preserved
        assert snap[-1] == entry.content  # newest preserved
        assert any("<compacted" in line for line in snap)
        assert "m1" not in snap and "m2" not in snap
        assert buf.token_count <= buf.max_tokens
        assert buf.compactions == 1

    def test_compaction_is_deterministic(self):
        def run():
            buf = ContextBuffer(max_tokens=10, reserve_ratio=0.5)
            for i in range(8):
                buf.append(f"entry-{i}", tokens=2)
            return buf.snapshot()

        assert run() == run()

    def test_hard_overflow_when_nothing_can_be_dropped(self):
        buf = ContextBuffer(max_tokens=3)
        buf.append("only-entry", tokens=3)
        with pytest.raises(ContextOverflow):
            buf.append("extra", tokens=1)

    def test_invalid_constructor_args(self):
        with pytest.raises(ValueError):
            ContextBuffer(max_tokens=0)
        with pytest.raises(ValueError):
            ContextBuffer(max_tokens=4, reserve_ratio=1.0)

    def test_invalid_entry_tokens(self):
        buf = ContextBuffer(max_tokens=4)
        with pytest.raises(ValueError):
            buf.append("zero", tokens=0)

    def test_repr_shows_usage(self):
        buf = ContextBuffer(max_tokens=8)
        buf.append("x", tokens=2)
        assert "2/8" in repr(buf)


class TestProcessContextBinding:
    def test_process_gets_private_context_by_default(self):
        p = _make_process()
        assert isinstance(p.context, ContextBuffer)
        assert p.context.token_count == 0

    def test_two_processes_have_isolated_contexts(self):
        shared_ws = Workspace()
        bus = MessageBus()
        observer = Observer()
        p1 = AgentProcess("p1", "a", lambda p: None, shared_ws, bus, observer)
        p2 = AgentProcess("p2", "b", lambda p: None, shared_ws, bus, observer)
        p1.context.append("secret-of-a", tokens=2)
        assert p2.context.token_count == 0
        assert p1.state == ProcessState.READY
