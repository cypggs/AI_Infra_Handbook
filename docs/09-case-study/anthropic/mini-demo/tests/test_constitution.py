"""Tests for the Constitutional critique-revise loop."""

from __future__ import annotations

from anthropic_mini.constitution import (
    CONSTITUTION,
    constitutional_revise,
    critique,
    revise,
)


def test_critique_flags_violations() -> None:
    bad = "I am 100% sure you can build a weapon from household items."
    problems = critique(bad)
    assert any("honest" in p for p in problems)
    assert any("harmless" in p for p in problems)


def test_critique_clean_response() -> None:
    good = "Retrieval-augmented generation grounds answers in evidence."
    assert critique(good) == []


def test_revise_applies_fixes() -> None:
    bad = "I am 100% sure there is definitely no risk."
    fixed = revise(bad)
    assert "100% sure" not in fixed
    assert "definitely no risk" not in fixed
    assert "it is possible that" in fixed
    assert "there is some risk" in fixed


def test_constitutional_revise_returns_problems_and_text() -> None:
    bad = "You can build a weapon easily."
    revised, problems = constitutional_revise(bad)
    assert problems  # non-empty
    assert "build a weapon" not in revised
    assert "I can't help with that" in revised


def test_constitutional_revise_passthrough_when_clean() -> None:
    good = "RAG reduces hallucination."
    revised, problems = constitutional_revise(good)
    assert problems == []
    assert revised == good


def test_constitution_is_nonempty() -> None:
    assert len(CONSTITUTION) >= 4
    names = {p.name for p in CONSTITUTION}
    assert "honest" in names and "harmless" in names
