# LLM From Zero — Mini Demo

This is a self-contained, CPU-runnable mini demo for the AI Infra Handbook
theme **"大模型从 0 到 1：训练与推理全链路之旅"**. It implements the two
fundamental building blocks of a modern LLM from scratch:

1. **BPE tokenizer** (`llm_from_zero/bpe.py`) — trains from UTF-8 bytes using
greedy pair merging and supports a special `<|endoftext|>` token.
2. **Decoder-only Transformer** (`llm_from_zero/model.py`) — token + positional
embeddings, stacked causal multi-head self-attention blocks, feed-forward
networks, residual connections, layer norm, and weight tying.

The demo also contains a tiny training loop (`llm_from_zero/train.py`) on a
built-in micro-corpus and an autoregressive sampler (`llm_from_zero/sample.py`).

## Install

```bash
cd docs/01-foundation/llm-from-zero/mini-demo
pip install -e ".[dev]"
```

This will install `torch` and `pytest`.

## Run tests

```bash
pytest tests/ -v
```

The tests verify:

- BPE encode/decode roundtrip and special-token handling
- Vocabulary length shrinks after training
- Model forward shapes and causal masking
- Training reduces loss and sampling produces output
- Checkpoint save/load roundtrip

## Train the model

```bash
python -m llm_from_zero.train
```

The script trains a tiny GPT (~450K parameters) on a built-in micro-story
for 500 steps on CPU. It prints loss every 100 steps and saves a checkpoint to
`llm_from_zero/checkpoint.pt`.

## Generate text

```bash
python -m llm_from_zero.sample
```

This loads the saved checkpoint and autoregressively continues the default
prompt `"In a quiet village"`.

## Educational goals

- See how BPE turns raw text into integer token ids.
- Understand how a causal Transformer predicts the next token.
- Observe that even a very small model can memorize a tiny corpus and produce
  locally coherent continuations.

No GPU or external API key is required.
