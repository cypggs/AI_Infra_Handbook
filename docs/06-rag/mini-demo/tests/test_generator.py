"""Tests for the mock generator."""

from rag_mini.documents import load_chunks
from rag_mini.generator import Generator


def test_generator_return_policy():
    chunks = load_chunks()
    generator = Generator()
    answer = generator.generate("What is the return policy?", chunks[:3])
    assert "thirty days" in answer.text
    assert answer.sources


def test_generator_warranty():
    chunks = load_chunks()
    generator = Generator()
    answer = generator.generate("Tell me about the warranty", chunks[:3])
    assert "one-year" in answer.text or "warranty" in answer.text.lower()


def test_generator_empty_context():
    generator = Generator()
    answer = generator.generate("What is the return policy?", [])
    assert "don't have enough information" in answer.text
    assert answer.sources == []


def test_generator_unknown_query():
    chunks = load_chunks()
    generator = Generator()
    answer = generator.generate("xyz123 unknown topic", chunks[:1])
    assert answer.sources
    assert "Based on the retrieved context" in answer.text


def test_generator_sources_match_context():
    chunks = load_chunks()
    generator = Generator()
    context = chunks[:2]
    answer = generator.generate("What is the return policy?", context)
    assert answer.sources == context
