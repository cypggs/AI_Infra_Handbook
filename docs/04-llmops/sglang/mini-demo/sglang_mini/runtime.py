"""A minimal SGLang-style runtime that combines RadixAttention and structured generation."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sglang_mini.cache_manager import RadixCacheManager
from sglang_mini.dummy_model import DummyModel
from sglang_mini.fsm import RegexFSM
from sglang_mini.structured_sampler import StructuredSampler


@dataclass
class GenerationRequest:
    request_id: str
    prompt_tokens: List[int]
    fsm: Optional[RegexFSM] = None
    max_new_tokens: int = 32
    generated_tokens: List[int] = field(default_factory=list)


class MiniRuntime:
    """Single-process runtime for the demo.

    Responsibilities:
    - Prefix matching via RadixCacheManager.
    - Dispatching one token at a time through the dummy model.
    - Applying structured generation constraints if provided.
    """

    def __init__(
        self,
        vocab: List[int],
        cache_manager: Optional[RadixCacheManager] = None,
        seed: int = 42,
    ):
        self.vocab = vocab
        self.cache = cache_manager or RadixCacheManager()
        self.model = DummyModel(vocab=vocab, seed=seed)

    def add_request(
        self,
        request_id: str,
        prompt_tokens: List[int],
        pattern: Optional[str] = None,
        max_new_tokens: int = 32,
    ) -> GenerationRequest:
        fsm = RegexFSM(pattern) if pattern else None
        self.cache.prepare_request(request_id, prompt_tokens)
        return GenerationRequest(
            request_id=request_id,
            prompt_tokens=prompt_tokens,
            fsm=fsm,
            max_new_tokens=max_new_tokens,
        )

    def generate(self, request: GenerationRequest) -> str:
        sampler = None
        if request.fsm is not None:
            sampler = StructuredSampler(
                fsm=request.fsm,
                vocab=self.vocab,
                temperature=0.0,
            )

        context = list(request.prompt_tokens)
        for _ in range(request.max_new_tokens):
            logits = self.model.logits(context)

            if sampler is not None:
                if sampler.is_done():
                    break
                token = sampler.next_token(logits)
            else:
                # Greedy decode when no constraint is given.
                token = int(torch.argmax(logits).item())  # type: ignore

            context.append(token)
            request.generated_tokens.append(token)

            if sampler is not None and not sampler.can_continue():
                break

        self.cache.commit_request(request.request_id)
        return "".join(chr(t) for t in request.generated_tokens if 32 <= t <= 126)

    def release(self, request: GenerationRequest) -> None:
        self.cache.release_request(request.request_id)

    def cache_stats(self) -> Dict[str, int]:
        return self.cache.stats()


# Dummy torch import kept local so the module can be imported without torch if needed.
import torch  # noqa: E402
