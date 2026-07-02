"""A tiny dummy language model for the Mini SGLang demo.

The model does not learn; it produces deterministic-ish logits so the demo
remains reproducible while still needing a sampler/FSM to steer output.
"""

from typing import List

import torch


class DummyModel:
    """Produces logits for a small vocabulary using a seeded hash.

    This is sufficient to demonstrate that the structured sampler can steer
    generation: even with random-ish logits, the output always follows the
    regex constraint.
    """

    def __init__(self, vocab: List[int], seed: int = 42):
        self.vocab = vocab
        self.seed = seed
        self._rng = torch.Generator()
        self._rng.manual_seed(seed)
        # Pre-generate a fixed preference vector so outputs are not uniform.
        self._prefs = torch.randn(len(vocab), generator=self._rng)

    def logits(self, context: List[int]) -> torch.Tensor:
        """Return a 1-D logits tensor for the current context."""
        # Mix in the context length and last token so logits evolve.
        bias = (len(context) * 0.1) + ((context[-1] if context else 0) * 0.01)
        return self._prefs + bias

    def reset(self) -> None:
        self._rng.manual_seed(self.seed)
