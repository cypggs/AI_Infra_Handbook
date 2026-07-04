"""Autoregressive text generation using a trained checkpoint."""

from __future__ import annotations

from pathlib import Path

import torch

from llm_from_zero.bpe import BPETokenizer, ENDOFTEXT
from llm_from_zero.model import GPT


DEFAULT_CKPT = Path(__file__).with_name("checkpoint.pt")


def load_model(checkpoint_path: str | Path, device: str | torch.device | None = None):
    """Load a tokenizer + model from a checkpoint produced by ``train.py``."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device)

    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    hparams = ckpt["hparams"]

    tokenizer = BPETokenizer(num_merges=ckpt["num_merges"])
    tokenizer.merges = ckpt["merges"]
    tokenizer.vocab = {int(k): v for k, v in ckpt["vocab"].items()}
    tokenizer.eot_id = ckpt["eot_id"]

    model = GPT(**hparams).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return tokenizer, model, hparams


def sample(
    prompt: str = "In a quiet village",
    checkpoint_path: str | Path = DEFAULT_CKPT,
    max_new_tokens: int = 100,
    temperature: float = 0.8,
    top_k: int = 10,
    seed: int | None = 42,
    device: str | torch.device | None = None,
) -> str:
    """Generate text from ``prompt`` using the checkpoint."""
    tokenizer, model, hparams = load_model(checkpoint_path, device=device)

    if seed is not None:
        torch.manual_seed(seed)

    if ENDOFTEXT in prompt:
        raise ValueError(f"Prompt must not contain the special token {ENDOFTEXT!r}")

    input_ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long, device=model.lm_head.weight.device)
    output_ids = model.generate(input_ids, max_new_tokens=max_new_tokens, temperature=temperature, top_k=top_k)
    generated = tokenizer.decode(output_ids[0].tolist())
    return generated


def main() -> None:
    """Entry point for ``python -m llm_from_zero.sample``."""
    prompt = "In a quiet village"
    print(f"Prompt: {prompt!r}")
    generated = sample(prompt=prompt, checkpoint_path=DEFAULT_CKPT)
    print("Generated:")
    print(generated)


if __name__ == "__main__":
    main()
