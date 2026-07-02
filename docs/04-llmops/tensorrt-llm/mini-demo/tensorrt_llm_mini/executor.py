"""Executor + Scheduler demonstrating In-flight Batching."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

from .engine import Engine
from .runtime import Runtime, SamplingParams


@dataclass
class Request:
    """A single inference request."""

    req_id: str
    prompt_ids: List[int]
    max_tokens: int
    sampling_params: SamplingParams = field(default_factory=SamplingParams)

    # Runtime state
    status: str = "waiting"  # waiting / running / finished
    tokens: List[int] = field(default_factory=list)
    kv_cache: Dict[str, Any] = field(default_factory=dict)
    is_prefill_done: bool = False
    context_pos: int = 0  # for chunked prefill simulation

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = []

    @property
    def all_tokens(self) -> List[int]:
        return self.prompt_ids + self.tokens


@dataclass
class Response:
    """Response for a finished request."""

    req_id: str
    tokens: List[int]


@dataclass
class SchedulerConfig:
    """IFB scheduler configuration."""

    max_batch_size: int = 8
    max_num_tokens: int = 256


class Executor:
    """Mini Executor that schedules requests using In-flight Batching."""

    def __init__(
        self,
        engine: Engine,
        scheduler_config: SchedulerConfig | None = None,
    ) -> None:
        self.engine = engine
        self.runtime = Runtime(engine)
        self.config = scheduler_config or SchedulerConfig()
        self.waiting: List[Request] = []
        self.running: List[Request] = []
        self.finished: List[Response] = []
        self.step_count = 0

    def submit(self, requests: List[Request]) -> None:
        for req in requests:
            req.kv_cache = self.runtime._make_kv_cache()
            self.waiting.append(req)

    def _make_kv_cache(self) -> Dict[str, Any]:
        return self.runtime._make_kv_cache()

    def _schedule(self) -> List[Request]:
        """Select requests for the current step.

        Generation-phase requests are scheduled first, then context-phase
        requests fill the remaining token budget.
        """
        selected: List[Request] = []
        tokens_used = 0

        # 1. Generation phase first (each consumes 1 token slot)
        still_running: List[Request] = []
        for req in self.running:
            if len(selected) < self.config.max_batch_size and tokens_used < self.config.max_num_tokens:
                selected.append(req)
                tokens_used += 1
            else:
                still_running.append(req)
        self.running = still_running

        # 2. Context phase from waiting queue
        still_waiting: List[Request] = []
        for req in self.waiting:
            needed = len(req.prompt_ids) - req.context_pos
            if (
                len(selected) < self.config.max_batch_size
                and tokens_used + needed <= self.config.max_num_tokens
            ):
                selected.append(req)
                tokens_used += needed
            else:
                still_waiting.append(req)
        self.waiting = still_waiting

        return selected

    def _run_forward(self, req: Request) -> int:
        """Run one forward step for ``req`` and return the new token."""
        if not req.is_prefill_done:
            # Prefill: process the whole prompt (or remaining chunk).
            input_ids = np.array([req.prompt_ids[req.context_pos:]], dtype=np.int64)
            logits = self.runtime._execute_graph(input_ids, req.kv_cache)
            req.is_prefill_done = True
        else:
            # Decode: process the last generated token.
            next_id = req.tokens[-1] if req.tokens else req.prompt_ids[-1]
            input_ids = np.array([[next_id]], dtype=np.int64)
            logits = self.runtime._execute_graph(input_ids, req.kv_cache)

        next_token = self.runtime._sample(logits[0, -1, :], req.sampling_params)
        return next_token

    def step(self) -> Dict[str, Any]:
        """Execute one IFB step and return scheduling metadata."""
        self.step_count += 1
        selected = self._schedule()

        context_ids = [r.req_id for r in selected if not r.is_prefill_done]
        generation_ids = [r.req_id for r in selected if r.is_prefill_done]

        for req in selected:
            next_token = self._run_forward(req)
            req.tokens.append(next_token)

            # Check completion
            if (
                len(req.tokens) >= req.max_tokens
                or next_token == req.sampling_params.eos_token_id
            ):
                req.status = "finished"
                self.finished.append(Response(req.req_id, req.tokens))
            else:
                req.status = "running"
                self.running.append(req)

        # Remove finished from running (they were added above only if not finished)
        self.running = [r for r in self.running if r.status != "finished"]

        return {
            "step": self.step_count,
            "context": context_ids,
            "generation": generation_ids,
            "scheduled": len(selected),
        }

    def generate_batch(
        self,
        requests: List[Request],
        max_steps: int = 1000,
    ) -> List[Response]:
        """Run until all submitted requests finish."""
        self.submit(requests)
        for _ in range(max_steps):
            if not self.waiting and not self.running:
                break
            self.step()
        return self.finished

    def reset(self) -> None:
        self.waiting = []
        self.running = []
        self.finished = []
        self.step_count = 0
