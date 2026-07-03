"""Tests for the chunking module."""

import pytest

from rag_mini.documents import chunk_text, load_chunks


def test_chunk_text_basic():
    text = "The quick brown fox jumps over the lazy dog"
    chunks = chunk_text(text, chunk_size=4, overlap=1)
    assert len(chunks) > 0
    assert chunks[0] == "The quick brown fox"
    # With overlap, next chunk should share one word with the previous chunk.
    assert "jumps" in chunks[1]


def test_chunk_text_overlap_less_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("some words", chunk_size=3, overlap=3)


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_load_chunks():
    chunks = load_chunks(chunk_size=20, overlap=5)
    assert len(chunks) > 0
    sections = {chunk.section for chunk in chunks}
    assert "returns" in sections
    assert "warranty" in sections
    assert "products" in sections
    assert "company-history" in sections


def test_chunk_ids_unique():
    chunks = load_chunks()
    ids = [chunk.id for chunk in chunks]
    assert len(ids) == len(set(ids))
