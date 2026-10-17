"""Tests for working memory truncation."""

from agent_runtime_mini.memory import WorkingMemory


def test_add_and_retrieve_messages():
    mem = WorkingMemory()
    mem.add_system_prompt("You are an agent.")
    mem.add_user_message("Hello")
    messages = mem.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_token_truncation_drops_oldest_non_system():
    mem = WorkingMemory(max_tokens=10)
    mem.add_system_prompt("system prompt")
    for i in range(10):
        mem.add_user_message(f"user message {i} with many tokens")

    assert mem.token_count() <= mem.max_tokens
    assert mem.messages[0]["role"] == "system"
    assert not any(m["content"] == "user message 0 with many tokens" for m in mem.messages)


def test_tool_messages():
    mem = WorkingMemory()
    mem.add_assistant_message("", tool_calls=[{"id": "1"}])
    mem.add_tool_message("1", "result")
    assert mem.messages[-1]["role"] == "tool"
    assert mem.messages[-1]["tool_call_id"] == "1"


def test_compact_summarizes_oldest_and_keeps_recent():
    mem = WorkingMemory(max_tokens=100000)
    mem.add_system_prompt("system prompt")
    for i in range(6):
        mem.add_user_message(f"message {i}")
    stats = mem.compact(keep_recent=2)
    assert stats["compacted"] == 4
    assert mem.messages[0]["role"] == "system"
    assert mem.messages[1]["compacted"] is True
    assert "4 messages" in mem.messages[1]["content"]
    assert mem.messages[-1]["content"] == "message 5"
    assert mem.token_count() <= 100000


def test_compact_is_deterministic():
    def summarizer(messages):
        return f"summary of {len(messages)}"

    mem1 = WorkingMemory(summarizer=summarizer)
    mem2 = WorkingMemory(summarizer=summarizer)
    for mem in (mem1, mem2):
        for i in range(5):
            mem.add_user_message(f"message {i}")
    mem1.compact(keep_recent=1)
    mem2.compact(keep_recent=1)
    assert mem1.get_messages() == mem2.get_messages()


def test_compact_noop_when_history_is_short():
    mem = WorkingMemory()
    mem.add_user_message("only one")
    stats = mem.compact()
    assert stats["compacted"] == 0
    assert len(mem.messages) == 1
