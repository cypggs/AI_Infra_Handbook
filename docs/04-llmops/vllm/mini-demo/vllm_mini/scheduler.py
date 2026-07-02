"""Continuous batching scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SequenceStatus(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    SWAPPED = "swapped"
    FINISHED = "finished"


@dataclass
class Sequence:
    """A single generation sequence."""

    seq_id: str
    prompt_tokens: List[int]
    max_output_len: int
    status: SequenceStatus = SequenceStatus.WAITING
    output_tokens: List[int] = field(default_factory=list)
    # position of the next token to compute
    next_position: int = 0

    def num_computed_tokens(self) -> int:
        return len(self.prompt_tokens) + len(self.output_tokens)

    def is_finished(self) -> bool:
        if self.status == SequenceStatus.FINISHED:
            return True
        if len(self.output_tokens) >= self.max_output_len:
            return True
        return False

    def append_token(self, token_id: int) -> None:
        self.output_tokens.append(token_id)

    def __hash__(self) -> int:
        return hash(self.seq_id)


@dataclass
class SequenceGroup:
    """A group of sequences sharing the same prompt (for beam search, simplified)."""

    group_id: str
    sequences: List[Sequence]
    arrival_time: float = 0.0


@dataclass
class SchedulerOutputs:
    """Output of one schedule() step."""

    scheduled_seq_groups: List[SequenceGroup] = field(default_factory=list)
    ignored_seq_groups: List[SequenceGroup] = field(default_factory=list)
    num_preempted: int = 0


class Scheduler:
    """Continuous batching scheduler with waiting/running/swapped queues."""

    def __init__(
        self,
        block_manager,
        max_num_seqs: int = 8,
        max_model_len: int = 256,
    ):
        self.block_manager = block_manager
        self.max_num_seqs = max_num_seqs
        self.max_model_len = max_model_len

        self.waiting: List[SequenceGroup] = []
        self.running: List[SequenceGroup] = []
        self.swapped: List[SequenceGroup] = []

        self._now: float = 0.0

    def add_seq_group(self, seq_group: SequenceGroup) -> None:
        seq_group.arrival_time = self._now
        self.waiting.append(seq_group)

    def _num_unfinished_seqs(self) -> int:
        return sum(
            1
            for sg in self.running + self.waiting + self.swapped
            for seq in sg.sequences
            if not seq.is_finished()
        )

    def schedule(self) -> SchedulerOutputs:
        """Run one scheduling step (iteration-level)."""
        outputs = SchedulerOutputs()

        # 1. Promote swapped sequences back to running if possible (simplified).
        # In a real system this involves CPU-GPU swap; here we just re-admit.
        still_swapped: List[SequenceGroup] = []
        for sg in self.swapped:
            can_run = True
            for seq in sg.sequences:
                needed = seq.num_computed_tokens()
                if not self.block_manager.can_allocate(needed):
                    can_run = False
                    break
            if can_run and len(self.running) < self.max_num_seqs:
                for seq in sg.sequences:
                    self.block_manager.allocate(seq.seq_id, seq.num_computed_tokens())
                    seq.status = SequenceStatus.RUNNING
                self.running.append(sg)
            else:
                still_swapped.append(sg)
        self.swapped = still_swapped

        # 2. Admit waiting sequences if resources allow.
        still_waiting: List[SequenceGroup] = []
        for sg in self.waiting:
            if len(self.running) >= self.max_num_seqs:
                still_waiting.append(sg)
                continue

            can_run = True
            for seq in sg.sequences:
                num_tokens = len(seq.prompt_tokens)
                if num_tokens > self.max_model_len:
                    outputs.ignored_seq_groups.append(sg)
                    can_run = False
                    break
                if not self.block_manager.can_allocate(num_tokens):
                    can_run = False
                    break

            if not can_run:
                still_waiting.append(sg)
                continue

            for seq in sg.sequences:
                self.block_manager.allocate(seq.seq_id, len(seq.prompt_tokens))
                seq.status = SequenceStatus.RUNNING
                seq.next_position = len(seq.prompt_tokens)
            self.running.append(sg)

        self.waiting = still_waiting

        # 3. Filter out finished sequences from running.
        new_running: List[SequenceGroup] = []
        for sg in self.running:
            active_seqs = [seq for seq in sg.sequences if not seq.is_finished()]
            if active_seqs:
                new_running.append(sg)
            else:
                # All sequences finished; free blocks.
                for seq in sg.sequences:
                    self.block_manager.free(seq.seq_id)
                    seq.status = SequenceStatus.FINISHED
        self.running = new_running

        outputs.scheduled_seq_groups = list(self.running)
        return outputs

    def update_model_outputs(self, outputs: Dict[str, int]) -> None:
        """Append sampled tokens to running sequences."""
        for sg in self.running:
            for seq in sg.sequences:
                if seq.is_finished():
                    continue
                token_id = outputs.get(seq.seq_id)
                if token_id is not None:
                    seq.append_token(token_id)
                    seq.next_position = seq.num_computed_tokens()
                    if seq.is_finished():
                        self.block_manager.free(seq.seq_id)
                        seq.status = SequenceStatus.FINISHED

    def has_unfinished_seqs(self) -> bool:
        return self._num_unfinished_seqs() > 0

    def stats(self) -> Dict[str, int]:
        return {
            "waiting": len(self.waiting),
            "running": len(self.running),
            "swapped": len(self.swapped),
            "unfinished_seqs": self._num_unfinished_seqs(),
        }
