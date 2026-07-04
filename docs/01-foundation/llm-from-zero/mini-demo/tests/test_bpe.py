"""Tests for the minimal BPE tokenizer."""

import pytest

from llm_from_zero.bpe import BPETokenizer, ENDOFTEXT


@pytest.fixture
def sample_text():
    return (
        "The quick brown fox jumps over the lazy dog. "
        "The lazy dog slept under the quick brown fox."
    )


def test_encode_decode_roundtrip(sample_text):
    tokenizer = BPETokenizer(num_merges=32).train(sample_text)
    ids = tokenizer.encode(sample_text)
    decoded = tokenizer.decode(ids)
    assert decoded == sample_text


def test_special_token_roundtrip():
    text = f"hello {ENDOFTEXT} world"
    tokenizer = BPETokenizer(num_merges=8).train(text)
    ids = tokenizer.encode(text)
    decoded = tokenizer.decode(ids)
    assert decoded == text
    assert tokenizer.eot_id in ids


def test_training_reduces_sequence_length(sample_text):
    tokenizer = BPETokenizer(num_merges=32).train(sample_text)
    raw_ids = list(sample_text.encode("utf-8"))
    trained_ids = tokenizer.encode(sample_text)
    # Merges should on average shorten the token sequence.
    assert len(trained_ids) < len(raw_ids)


def test_vocab_size_includes_special_token(sample_text):
    tokenizer = BPETokenizer(num_merges=50).train(sample_text)
    # 256 byte tokens + learned merges + 1 special token.
    assert tokenizer.vocab_size == 256 + tokenizer.num_merges + 1


def test_untrained_tokenizer_raises():
    tokenizer = BPETokenizer(num_merges=10)
    with pytest.raises(RuntimeError):
        tokenizer.encode("hello")
    with pytest.raises(RuntimeError):
        tokenizer.decode([0])
