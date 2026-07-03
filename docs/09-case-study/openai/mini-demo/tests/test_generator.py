from openai_mini.generator import complete, generate


def test_generate_returns_words():
    tokens = generate("gpt-mini", "Hi")
    assert isinstance(tokens, list)
    assert len(tokens) >= 3


def test_generate_includes_prompt():
    tokens = generate("gpt-mini", "test-prompt")
    assert "'test-prompt')" in tokens[-1]


def test_complete():
    text = complete("gpt-large", "Hello")
    assert "Greetings from gpt-large" in text
    assert "'Hello')" in text
