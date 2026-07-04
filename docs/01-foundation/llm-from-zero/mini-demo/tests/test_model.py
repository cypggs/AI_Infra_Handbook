"""Tests for the minimal decoder-only Transformer."""

import pytest
import torch

from llm_from_zero.model import GPT


@pytest.fixture
def tiny_gpt():
    return GPT(vocab_size=300, block_size=16, n_embed=32, n_head=4, n_layer=2)


def test_forward_shape(tiny_gpt):
    batch, seq = 2, 8
    idx = torch.randint(0, tiny_gpt.vocab_size, (batch, seq))
    logits = tiny_gpt(idx)
    assert logits.shape == (batch, seq, tiny_gpt.vocab_size)


def test_forward_loss(tiny_gpt):
    batch, seq = 2, 8
    idx = torch.randint(0, tiny_gpt.vocab_size, (batch, seq))
    targets = torch.randint(0, tiny_gpt.vocab_size, (batch, seq))
    loss = tiny_gpt(idx, targets)
    assert loss.shape == ()
    assert loss.item() > 0


def test_causal_mask_blocks_future(tiny_gpt):
    """The model should be invariant to future tokens."""
    tiny_gpt.eval()
    with torch.no_grad():
        prefix = torch.randint(0, tiny_gpt.vocab_size, (1, 4))
        # Two different future tokens appended to the same prefix.
        future_a = torch.randint(0, tiny_gpt.vocab_size, (1, 4))
        future_b = torch.randint(0, tiny_gpt.vocab_size, (1, 4))

        input_a = torch.cat([prefix, future_a], dim=1)
        input_b = torch.cat([prefix, future_b], dim=1)

        logits_a = tiny_gpt(input_a)
        logits_b = tiny_gpt(input_b)

        # Logits for the prefix positions must be identical regardless of future.
        torch.testing.assert_close(logits_a[:, :4, :], logits_b[:, :4, :])
        # Future positions may differ.
        assert not torch.allclose(logits_a[:, 4:, :], logits_b[:, 4:, :])


def test_generate_shape(tiny_gpt):
    tiny_gpt.eval()
    idx = torch.randint(0, tiny_gpt.vocab_size, (1, 4))
    out = tiny_gpt.generate(idx, max_new_tokens=6)
    assert out.shape == (1, 4 + 6)
