"""Tests for the training and sampling pipeline."""

import tempfile
from pathlib import Path

import pytest
import torch

from llm_from_zero.bpe import BPETokenizer
from llm_from_zero.model import GPT
from llm_from_zero.sample import sample
from llm_from_zero.train import TINY_CORPUS, train


def test_training_reduces_loss():
    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = Path(tmpdir) / "checkpoint.pt"
        model, tokenizer, hparams = train(
            text=TINY_CORPUS,
            num_merges=16,
            batch_size=4,
            max_steps=30,
            learning_rate=5e-4,
            block_size=32,
            eval_interval=1000,  # silence during test
            checkpoint_path=ckpt,
            device="cpu",
        )
        # Just run a quick forward pass on the full corpus to get final loss.
        token_ids = tokenizer.encode(TINY_CORPUS)
        dataset_size = len(token_ids) - hparams["block_size"]
        losses: list[float] = []
        model.eval()
        with torch.no_grad():
            for i in range(0, min(dataset_size, 200), hparams["block_size"]):
                x = torch.tensor(token_ids[i : i + hparams["block_size"]], dtype=torch.long).unsqueeze(0)
                y = torch.tensor(
                    token_ids[i + 1 : i + hparams["block_size"] + 1], dtype=torch.long
                ).unsqueeze(0)
                loss = model(x.to(model.lm_head.weight.device), y.to(model.lm_head.weight.device))
                losses.append(loss.item())
        final_loss = sum(losses) / len(losses)
        # After training the model should have learned something non-trivial.
        assert final_loss < 4.0


def test_sampling_produces_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = Path(tmpdir) / "checkpoint.pt"
        train(
            text=TINY_CORPUS,
            num_merges=16,
            batch_size=4,
            max_steps=30,
            learning_rate=5e-4,
            block_size=32,
            eval_interval=1000,
            checkpoint_path=ckpt,
            device="cpu",
        )
        generated = sample(
            prompt="In a quiet village",
            checkpoint_path=ckpt,
            max_new_tokens=20,
            temperature=0.8,
            top_k=10,
            seed=0,
            device="cpu",
        )
        assert isinstance(generated, str)
        assert len(generated) > len("In a quiet village")


def test_checkpoint_save_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = Path(tmpdir) / "checkpoint.pt"
        _, tokenizer, hparams = train(
            text=TINY_CORPUS,
            num_merges=16,
            batch_size=4,
            max_steps=10,
            learning_rate=5e-4,
            block_size=32,
            eval_interval=1000,
            checkpoint_path=ckpt,
            device="cpu",
        )
        assert ckpt.exists()

        loaded = torch.load(ckpt, weights_only=False)
        assert loaded["hparams"] == hparams
        assert loaded["eot_id"] == tokenizer.eot_id
