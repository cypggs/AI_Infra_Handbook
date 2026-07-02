import pytest

from agent_memory_mini.working_memory import WorkingMemory


def test_add_and_get_messages():
    wm = WorkingMemory()
    wm.add_message("system", "sys")
    wm.add_message("user", "hello")
    messages = wm.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "system"


def test_clear_working_memory():
    wm = WorkingMemory()
    wm.add_message("user", "hello")
    wm.clear()
    assert wm.get_messages() == []


def test_truncate_preserves_system_messages():
    wm = WorkingMemory(budget=10, budget_mode="char")
    wm.add_message("system", "system prompt")
    wm.add_message("user", "hello world")  # 11 chars, exceeds budget
    wm.add_message("assistant", "hi")
    wm.truncate_to_budget(preserve_system=True)
    roles = [m["role"] for m in wm.get_messages()]
    assert roles[0] == "system"
    assert "user" not in roles


def test_truncate_word_mode():
    wm = WorkingMemory(budget=3, budget_mode="word")
    wm.add_message("user", "one two three")
    wm.add_message("assistant", "four five six")
    wm.truncate_to_budget(preserve_system=False)
    assert len(wm.get_messages()) == 1


def test_invalid_budget_mode():
    with pytest.raises(ValueError):
        WorkingMemory(budget_mode="token")
