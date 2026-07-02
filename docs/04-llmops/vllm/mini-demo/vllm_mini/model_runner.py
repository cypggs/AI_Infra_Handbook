"""Model runner with a tiny dummy model for demonstration."""

from __future__ import annotations

from typing import Dict, List

import torch
import torch.nn as nn


class DummyModel(nn.Module):
    """A tiny language model for demonstration only.

    It maps token ids to logits using a small embedding + linear layer.
    No real attention is performed; the goal is to simulate a forward pass.
    """

    def __init__(self, vocab_size: int = 128, hidden_size: int = 64):
        super().__init__()
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)
        # Make output deterministic for the demo
        torch.manual_seed(42)
        nn.init.xavier_uniform_(self.embedding.weight)
        nn.init.xavier_uniform_(self.lm_head.weight)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Return logits of shape [batch_size, vocab_size]."""
        x = self.embedding(input_ids)
        # For prefill we only care about the last token logits.
        x = x[:, -1, :]
        logits = self.lm_head(x)
        return logits


class Sampler:
    """Greedy sampler."""

    def __init__(self, device: torch.device):
        self.device = device

    def sample(self, logits: torch.Tensor) -> torch.Tensor:
        return torch.argmax(logits, dim=-1)


class ModelRunner:
    """Coordinates forward pass and sampling."""

    def __init__(self, vocab_size: int = 128, hidden_size: int = 64, device: torch.device = None):
        self.device = device or torch.device("cpu")
        self.model = DummyModel(vocab_size, hidden_size).to(self.device)
        self.sampler = Sampler(self.device)
        self.vocab_size = vocab_size

    def execute(
        self,
        input_tokens: Dict[str, List[int]],
    ) -> Dict[str, int]:
        """Run one forward step for a batch of sequences.

        Args:
            input_tokens: mapping from seq_id to token ids to feed into the model.

        Returns:
            mapping from seq_id to sampled token id.
        """
        if not input_tokens:
            return {}

        seq_ids = list(input_tokens.keys())
        token_lists = [input_tokens[sid] for sid in seq_ids]
        max_len = max(len(t) for t in token_lists)

        # Pad to max length within the batch.
        padded = []
        for tokens in token_lists:
            padded.append(tokens + [0] * (max_len - len(tokens)))

        input_tensor = torch.tensor(padded, dtype=torch.long, device=self.device)
        with torch.no_grad():
            logits = self.model(input_tensor)
            next_tokens = self.sampler.sample(logits)

        return {seq_ids[i]: int(next_tokens[i].item()) for i in range(len(seq_ids))}
