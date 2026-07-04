"""Training loop for the minimal GPT demo.

Uses a tiny built-in corpus so the demo is self-contained and trains on CPU in
under a minute.  The model learns character/byte-level patterns via the BPE
tokenizer trained on the same corpus.
"""

from __future__ import annotations

import os
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

from llm_from_zero.bpe import BPETokenizer, ENDOFTEXT
from llm_from_zero.model import GPT


# A tiny self-contained corpus.  The model will overfit and learn local
# structure quickly, which is perfect for a CPU demo.
TINY_CORPUS = """\
In a quiet village by the sea, a young inventor built a clockwork bird.
Every morning the bird sang a new song, and every evening it told a story.
The villagers gathered to listen, for the bird's tales carried hope across
the salty wind. <|endoftext|>
Far away, a stargazer mapped the night sky with copper gears and silver ink.
She believed every star was a question waiting for a brave answer.
When the clockwork bird met the stargazer, their questions became songs
and their songs became light. <|endoftext|>
"""

DEFAULT_CKPT = Path(__file__).with_name("checkpoint.pt")


class TextDataset(Dataset):
    """Slide a window of length ``block_size`` over tokenized text."""

    def __init__(self, token_ids: list[int], block_size: int):
        self.data = token_ids
        self.block_size = block_size

    def __len__(self) -> int:
        return max(0, len(self.data) - self.block_size)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        chunk = self.data[idx : idx + self.block_size + 1]
        x = torch.tensor(chunk[:-1], dtype=torch.long)
        y = torch.tensor(chunk[1:], dtype=torch.long)
        return x, y


def get_default_hparams(vocab_size: int, block_size: int = 64) -> dict:
    """Return small hyperparameters suitable for CPU demo training."""
    return {
        "vocab_size": vocab_size,
        "block_size": block_size,
        "n_embed": 128,
        "n_head": 4,
        "n_layer": 2,
        "dropout": 0.1,
    }


def train(
    text: str | None = None,
    num_merges: int = 64,
    batch_size: int = 8,
    max_steps: int = 500,
    learning_rate: float = 5e-4,
    block_size: int = 64,
    eval_interval: int = 100,
    checkpoint_path: str | os.PathLike = DEFAULT_CKPT,
    device: str | torch.device | None = None,
) -> tuple[GPT, BPETokenizer, dict]:
    """Train a tiny GPT on the built-in corpus.

    Returns the trained model, tokenizer, and hyperparameter dict.
    """
    text = text if text is not None else TINY_CORPUS
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device)
    print(f"Using device: {device}")

    # Train BPE tokenizer directly on the corpus.
    tokenizer = BPETokenizer(num_merges=num_merges).train(text)
    print(f"Tokenizer vocab size: {tokenizer.vocab_size}")

    token_ids = tokenizer.encode(text)
    hparams = get_default_hparams(tokenizer.vocab_size, block_size=block_size)

    model = GPT(**hparams).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    dataset = TextDataset(token_ids, block_size=block_size)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    model.train()
    step = 0
    losses: list[float] = []
    while step < max_steps:
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = model(xb, yb)
            loss.backward()
            optimizer.step()

            losses.append(loss.item())
            if step % eval_interval == 0:
                print(f"step {step:4d} | loss {loss.item():.4f}")
            step += 1
            if step >= max_steps:
                break

    # Save checkpoint: model weights + tokenizer merges + hyperparameters.
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "merges": tokenizer.merges,
        "vocab": tokenizer.vocab,
        "eot_id": tokenizer.eot_id,
        "num_merges": tokenizer.num_merges,
        "hparams": hparams,
    }
    torch.save(checkpoint, checkpoint_path)
    print(f"Saved checkpoint to {checkpoint_path}")
    print(f"Final step {step} | loss {losses[-1]:.4f}")

    return model, tokenizer, hparams


def main() -> None:
    """Entry point for ``python -m llm_from_zero.train``."""
    train(
        text=TINY_CORPUS,
        num_merges=64,
        batch_size=8,
        max_steps=500,
        learning_rate=5e-4,
        block_size=64,
        eval_interval=100,
        checkpoint_path=DEFAULT_CKPT,
    )


if __name__ == "__main__":
    main()
