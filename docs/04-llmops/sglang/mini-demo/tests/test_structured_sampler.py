"""Tests for the FSM-based structured sampler."""

import torch

from sglang_mini.fsm import RegexFSM
from sglang_mini.structured_sampler import StructuredSampler


def _vocab(chars: str):
    return [ord(c) for c in chars]


def test_date_pattern():
    fsm = RegexFSM(r"\d{4}-\d{2}-\d{2}")
    vocab = _vocab("0123456789-")
    sampler = StructuredSampler(fsm=fsm, vocab=vocab, temperature=0.0)

    output = []
    for _ in range(20):
        logits = torch.randn(len(vocab))
        token = sampler.next_token(logits)
        output.append(chr(token))
        if sampler.is_done():
            break

    text = "".join(output)
    assert len(text) == 10
    assert text[4] == "-"
    assert text[7] == "-"
    assert text.replace("-", "").isdigit()


def test_alternation_pattern():
    fsm = RegexFSM("(red|blue)")
    vocab = _vocab("redblue")
    sampler = StructuredSampler(fsm=fsm, vocab=vocab, temperature=0.0)

    output = []
    for _ in range(10):
        logits = torch.randn(len(vocab))
        token = sampler.next_token(logits)
        output.append(chr(token))
        if sampler.is_done():
            break

    text = "".join(output)
    assert text in ("red", "blue")


def test_allowed_tokens_shrink_then_expand():
    """For A(B|C)+, the first token must be A; after that B or C are allowed."""
    fsm = RegexFSM("A(B|C)+")
    vocab = _vocab("ABC")
    sampler = StructuredSampler(fsm=fsm, vocab=vocab, temperature=0.0)

    # First step only 'A' is legal.
    logits = torch.zeros(len(vocab))
    first = sampler.next_token(logits)
    assert chr(first) == "A"

    # Next steps only B or C are legal (greedy picks the first allowed).
    second = sampler.next_token(logits)
    assert chr(second) in ("B", "C")


def test_temperature_zero_greedy():
    fsm = RegexFSM("AB")
    vocab = _vocab("AB")
    # Make 'B' look much better than 'A'.
    logits = torch.tensor([1.0, 100.0])
    sampler = StructuredSampler(fsm=fsm, vocab=vocab, temperature=0.0)
    token = sampler.next_token(logits)
    assert chr(token) == "A"  # constraint overrides high logit for B
