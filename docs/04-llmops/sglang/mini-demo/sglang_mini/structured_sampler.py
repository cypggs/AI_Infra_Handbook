"""A constrained sampler that combines an FSM with model logits.

At each step the sampler builds a mask of FSM-legal tokens, masks out illegal
tokens, and then samples from the remaining distribution.
"""

from typing import FrozenSet, List

import torch

from sglang_mini.fsm import RegexFSM, State


class StructuredSampler:
    """Sample tokens while obeying a regex-like FSM constraint."""

    def __init__(
        self,
        fsm: RegexFSM,
        vocab: List[int],
        temperature: float = 1.0,
    ):
        self.fsm = fsm
        self.vocab = vocab
        self.temperature = temperature
        self.current_states: FrozenSet[State] = fsm.initial_states()
        self.generated: List[int] = []

    def is_done(self) -> bool:
        return self.fsm.is_accepting(self.current_states)

    def can_continue(self) -> bool:
        return self.fsm.can_finish(self.current_states)

    def next_token(self, logits: torch.Tensor) -> int:
        """Return the next token id respecting the FSM.

        Args:
            logits: 1-D tensor of logits for every token in ``self.vocab``.
                    The indices correspond to the order of ``self.vocab``.
        """
        allowed = self.fsm.allowed_tokens(self.current_states, self.vocab)
        if not allowed:
            raise RuntimeError(
                f"FSM has no legal token from states {self.current_states}; "
                f"generated so far: {''.join(chr(t) for t in self.generated)}"
            )

        allowed_set = set(allowed)
        mask = torch.tensor(
            [1.0 if token in allowed_set else 0.0 for token in self.vocab],
            dtype=logits.dtype,
        )

        masked_logits = logits.clone()
        masked_logits[mask == 0.0] = float("-inf")

        if self.temperature > 0 and self.temperature != 1.0:
            masked_logits = masked_logits / self.temperature

        if self.temperature == 0:
            idx = int(torch.argmax(masked_logits).item())
        else:
            probs = torch.softmax(masked_logits, dim=-1)
            idx = int(torch.multinomial(probs, num_samples=1).item())

        token = self.vocab[idx]
        self.current_states = self.fsm.step(self.current_states, token)
        self.generated.append(token)
        return token

    def reset(self) -> None:
        self.current_states = self.fsm.initial_states()
        self.generated.clear()

    def decode(self) -> str:
        return "".join(chr(t) for t in self.generated if 32 <= t <= 126)
