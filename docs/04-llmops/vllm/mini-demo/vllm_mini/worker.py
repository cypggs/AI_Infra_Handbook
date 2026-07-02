"""Worker: prepares inputs and invokes the model runner."""

from __future__ import annotations

from typing import Dict, List

import torch

from vllm_mini.model_runner import ModelRunner
from vllm_mini.paged_attention import BlockManager
from vllm_mini.scheduler import Sequence, SequenceGroup


class Worker:
    """A single worker that owns a model runner and a block manager."""

    def __init__(
        self,
        block_manager: BlockManager,
        vocab_size: int = 128,
        hidden_size: int = 64,
        device: torch.device = None,
    ):
        self.block_manager = block_manager
        self.model_runner = ModelRunner(vocab_size, hidden_size, device)
        self.device = device or torch.device("cpu")

    def execute_model(
        self,
        scheduled_seq_groups: List[SequenceGroup],
    ) -> Dict[str, int]:
        """Run one model step for the scheduled sequences.

        For each sequence, we read its full token history (prompt + generated)
        and write the new KV into the paged cache.
        """
        input_tokens: Dict[str, List[int]] = {}

        for sg in scheduled_seq_groups:
            for seq in sg.sequences:
                if seq.is_finished():
                    continue
                # Collect all tokens seen so far.
                all_tokens = seq.prompt_tokens + seq.output_tokens
                input_tokens[seq.seq_id] = all_tokens

        # Forward pass.
        next_tokens = self.model_runner.execute(input_tokens)

        # Write KV for the newly generated token.
        # In a real implementation this would come from the model forward.
        # Here we generate dummy KV and store it in the block manager.
        for sg in scheduled_seq_groups:
            for seq in sg.sequences:
                if seq.seq_id not in next_tokens or seq.is_finished():
                    continue
                token_id = next_tokens[seq.seq_id]
                pos = seq.num_computed_tokens()
                k = torch.randn(
                    self.model_runner.model.hidden_size, device=self.device
                ).view(self.block_manager.num_heads, self.block_manager.head_size)
                v = torch.randn(
                    self.model_runner.model.hidden_size, device=self.device
                ).view(self.block_manager.num_heads, self.block_manager.head_size)
                self.block_manager.write_kv(seq.seq_id, pos, k, v)

        return next_tokens
