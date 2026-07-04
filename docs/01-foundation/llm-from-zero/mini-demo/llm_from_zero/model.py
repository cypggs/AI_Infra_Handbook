"""Minimal decoder-only Transformer language model.

The architecture follows the original "Attention Is All You Need" decoder stack:
learned token embeddings, learned positional embeddings, stacked Transformer
blocks (causal multi-head self-attention + feed-forward network + residual
connections + layer norm), and a final projection tied to the input token
embeddings.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class CausalSelfAttention(nn.Module):
    """Multi-head causal self-attention with scaled dot-product attention."""

    def __init__(self, n_embed: int, n_head: int, block_size: int, dropout: float):
        super().__init__()
        assert n_embed % n_head == 0, "Embedding dimension must be divisible by n_head."
        self.n_head = n_head
        self.n_embed = n_embed
        self.head_size = n_embed // n_head

        # Single linear projection that produces Q, K, V together.
        self.c_attn = nn.Linear(n_embed, 3 * n_embed)
        self.c_proj = nn.Linear(n_embed, n_embed)
        self.attn_dropout = nn.Dropout(dropout)
        self.resid_dropout = nn.Dropout(dropout)

        # Causal mask: True for positions that should be masked (the future).
        self.register_buffer(
            "mask",
            torch.tril(torch.ones(block_size, block_size)).view(
                1, 1, block_size, block_size
            )
            == 0,
        )

    def forward(self, x: Tensor) -> Tensor:
        b, t, c = x.size()

        # Compute Q, K, V and reshape for multi-head attention.
        qkv = self.c_attn(x)  # (b, t, 3*c)
        q, k, v = qkv.split(self.n_embed, dim=2)
        q = q.view(b, t, self.n_head, self.head_size).transpose(1, 2)  # (b, h, t, hs)
        k = k.view(b, t, self.n_head, self.head_size).transpose(1, 2)
        v = v.view(b, t, self.n_head, self.head_size).transpose(1, 2)

        # Scaled dot-product attention.
        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_size))
        att = att.masked_fill(self.mask[:, :, :t, :t], float("-inf"))
        att = F.softmax(att, dim=-1)
        att = self.attn_dropout(att)
        y = att @ v  # (b, h, t, hs)

        # Re-assemble and project.
        y = y.transpose(1, 2).contiguous().view(b, t, c)
        y = self.resid_dropout(self.c_proj(y))
        return y


class TransformerBlock(nn.Module):
    """One decoder block: pre-norm causal self-attention + FFN."""

    def __init__(self, n_embed: int, n_head: int, block_size: int, dropout: float):
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embed)
        self.attn = CausalSelfAttention(n_embed, n_head, block_size, dropout)
        self.ln2 = nn.LayerNorm(n_embed)
        self.mlp = nn.Sequential(
            nn.Linear(n_embed, 4 * n_embed),
            nn.GELU(),
            nn.Linear(4 * n_embed, n_embed),
            nn.Dropout(dropout),
        )

    def forward(self, x: Tensor) -> Tensor:
        # Pre-norm residual connections.
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    """Tiny decoder-only Transformer for CPU demo training.

    Args:
        vocab_size: Size of the tokenizer vocabulary.
        block_size: Maximum sequence length.
        n_embed: Embedding dimension.
        n_head: Number of attention heads.
        n_layer: Number of Transformer blocks.
        dropout: Dropout probability.
    """

    def __init__(
        self,
        vocab_size: int,
        block_size: int = 128,
        n_embed: int = 128,
        n_head: int = 4,
        n_layer: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.block_size = block_size
        self.vocab_size = vocab_size

        self.token_embedding = nn.Embedding(vocab_size, n_embed)
        self.position_embedding = nn.Embedding(block_size, n_embed)
        self.dropout = nn.Dropout(dropout)
        self.blocks = nn.Sequential(
            *[TransformerBlock(n_embed, n_head, block_size, dropout) for _ in range(n_layer)]
        )
        self.ln_f = nn.LayerNorm(n_embed)
        self.lm_head = nn.Linear(n_embed, vocab_size, bias=False)

        # Weight tying between token embedding and final projection.
        self.lm_head.weight = self.token_embedding.weight

        self.apply(self._init_weights)
        # Report parameter count for educational value.
        n_params = sum(p.numel() for p in self.parameters())
        print(f"GPT model parameters: {n_params:,}")

    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx: Tensor, targets: Tensor | None = None) -> Tensor:
        """Forward pass.

        Args:
            idx: Input token ids of shape (batch, sequence_len).
            targets: Optional target token ids of the same shape for loss.

        Returns:
            Logits tensor of shape (batch, sequence_len, vocab_size) if
            ``targets`` is None, otherwise the scalar cross-entropy loss.
        """
        b, t = idx.size()
        assert t <= self.block_size, f"Sequence length {t} exceeds block size {self.block_size}"

        tok_emb = self.token_embedding(idx)  # (b, t, c)
        pos = torch.arange(0, t, dtype=torch.long, device=idx.device).unsqueeze(0)  # (1, t)
        pos_emb = self.position_embedding(pos)
        x = self.dropout(tok_emb + pos_emb)
        x = self.blocks(x)
        x = self.ln_f(x)
        logits = self.lm_head(x)  # (b, t, vocab_size)

        if targets is None:
            return logits

        loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
        return loss

    @torch.no_grad()
    def generate(
        self,
        idx: Tensor,
        max_new_tokens: int,
        temperature: float = 1.0,
        top_k: int | None = None,
    ) -> Tensor:
        """Generate tokens autoregressively.

        Args:
            idx: Starting token ids of shape (batch, sequence_len).
            max_new_tokens: Number of new tokens to generate.
            temperature: Sampling temperature.
            top_k: If set, only sample from the top-k logits.

        Returns:
            Tensor of shape (batch, sequence_len + max_new_tokens).
        """
        self.eval()
        for _ in range(max_new_tokens):
            # Crop to block size.
            idx_cond = idx[:, -self.block_size :]
            logits = self(idx_cond)
            # Take logits for the last position.
            logits = logits[:, -1, :] / temperature
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")
            probs = F.softmax(logits, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, next_id), dim=1)
        return idx
