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
