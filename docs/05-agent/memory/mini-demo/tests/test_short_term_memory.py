from agent_memory_mini.short_term_memory import ShortTermMemory


def test_sliding_window_summarizes_old_turns():
    stm = ShortTermMemory(max_turns=4)
    for i in range(6):
        stm.add_turn(f"question {i}", f"answer {i}")
    assert len(stm.recent_turns) <= 4
    context = stm.get_context()
    assert "Summary:" in context


def test_session_summary_storage():
    stm = ShortTermMemory()
    messages = [
        {"role": "user", "content": "I like Python"},
        {"role": "assistant", "content": "Noted."},
    ]
    stm.add_session("s1", messages)
    session = stm.get_session("s1")
    assert session is not None
    assert "summary" in session
    assert stm.forget_session("s1") is True
    assert stm.get_session("s1") is None


def test_summarizer_prefers_frequent_words():
    stm = ShortTermMemory(max_turns=10)
    text = "Python is great. Java is verbose. Python is easy to learn."
    stm.add_turn("tell me about languages", text)
    summary = stm.summarizer.summarize(text, max_sentences=2)
    assert "Python" in summary
