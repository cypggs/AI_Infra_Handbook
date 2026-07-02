"""Tests for the generator agent."""

from reflection_mini.generator import GeneratorAgent
from reflection_mini.workspace import Workspace


REQUEST = "Explain Agent Reflection in one paragraph"


def test_produce_writes_draft_and_latest():
    ws = Workspace()
    generator = GeneratorAgent()
    draft = generator.produce(REQUEST, ws, iteration=0)

    assert "v1" in draft
    assert ws.read("draft_v0") == draft
    assert ws.read("latest_draft") == draft


def test_revised_draft_differs_after_critique():
    ws = Workspace()
    generator = GeneratorAgent()

    first = generator.produce(REQUEST, ws, iteration=0)
    ws.write("latest_critique", ["缺少具体例子"])
    second = generator.produce(REQUEST, ws, iteration=1)

    assert first != second
    assert "example" in second.lower()
    assert "缺少具体例子" in second
