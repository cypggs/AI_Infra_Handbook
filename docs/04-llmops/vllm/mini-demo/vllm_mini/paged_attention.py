"""PagedAttention: block-based KV cache management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch


@dataclass
class Block:
    """A physical block holding KV cache for up to block_size tokens."""

    block_id: int
    block_size: int
    num_heads: int
    head_size: int
    device: torch.device
    ref_count: int = 0
    k_cache: torch.Tensor = field(init=False)
    v_cache: torch.Tensor = field(init=False)

    def __post_init__(self):
        self.k_cache = torch.zeros(
            self.block_size, self.num_heads, self.head_size, device=self.device
        )
        self.v_cache = torch.zeros(
            self.block_size, self.num_heads, self.head_size, device=self.device
        )

    def add_ref(self) -> None:
        self.ref_count += 1

    def dec_ref(self) -> None:
        assert self.ref_count > 0
        self.ref_count -= 1


class BlockManager:
    """Manages physical blocks and per-sequence block tables."""

    def __init__(
        self,
        num_blocks: int,
        block_size: int,
        num_heads: int,
        head_size: int,
        device: torch.device,
    ):
        self.block_size = block_size
        self.num_heads = num_heads
        self.head_size = head_size
        self.device = device
        self._blocks: Dict[int, Block] = {
            i: Block(i, block_size, num_heads, head_size, device)
            for i in range(num_blocks)
        }
        self._free_blocks: List[int] = list(range(num_blocks))
        # seq_id -> ordered list of physical block ids
        self._block_tables: Dict[str, List[int]] = {}

    def allocate(self, seq_id: str, num_tokens: int) -> List[int]:
        """Allocate new blocks for a sequence (initial prefill)."""
        if seq_id in self._block_tables:
            raise ValueError(f"Sequence {seq_id} already has a block table")

        num_blocks_needed = (num_tokens + self.block_size - 1) // self.block_size
        if num_blocks_needed > len(self._free_blocks):
            raise RuntimeError("Out of free blocks")

        block_table: List[int] = []
        for _ in range(num_blocks_needed):
            bid = self._free_blocks.pop()
            block = self._blocks[bid]
            block.add_ref()
            block_table.append(bid)

        self._block_tables[seq_id] = block_table
        return block_table

    def append_slot(self, seq_id: str, token_position: int) -> int:
        """Return the physical block id for a new token, allocating if needed."""
        block_table = self._block_tables[seq_id]
        block_idx = token_position // self.block_size

        if block_idx >= len(block_table):
            if not self._free_blocks:
                raise RuntimeError("Out of free blocks")
            bid = self._free_blocks.pop()
            self._blocks[bid].add_ref()
            block_table.append(bid)

        return block_table[block_idx]

    def get_block_table(self, seq_id: str) -> List[int]:
        return list(self._block_tables.get(seq_id, []))

    def num_free_blocks(self) -> int:
        return len(self._free_blocks)

    def free(self, seq_id: str) -> None:
        """Release all blocks held by a sequence."""
        if seq_id not in self._block_tables:
            return
        for bid in self._block_tables[seq_id]:
            block = self._blocks[bid]
            block.dec_ref()
            if block.ref_count == 0:
                self._free_blocks.append(bid)
        del self._block_tables[seq_id]

    def get_kv(self, seq_id: str, token_position: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Read KV for a specific token position (for decode attention)."""
        block_table = self._block_tables[seq_id]
        block_idx = token_position // self.block_size
        offset = token_position % self.block_size
        bid = block_table[block_idx]
        block = self._blocks[bid]
        return block.k_cache[offset], block.v_cache[offset]

    def write_kv(
        self,
        seq_id: str,
        token_position: int,
        k: torch.Tensor,
        v: torch.Tensor,
    ) -> None:
        """Write KV for a specific token position."""
        self.append_slot(seq_id, token_position)
        block_table = self._block_tables[seq_id]
        block_idx = token_position // self.block_size
        offset = token_position % self.block_size
        bid = block_table[block_idx]
        block = self._blocks[bid]
        block.k_cache[offset] = k
        block.v_cache[offset] = v

    def can_allocate(self, num_tokens: int) -> bool:
        """Check if we can allocate blocks for a new sequence."""
        num_blocks_needed = (num_tokens + self.block_size - 1) // self.block_size
        return num_blocks_needed <= len(self._free_blocks)

    def block_usage(self) -> Tuple[int, int]:
        """Return (used_blocks, total_blocks)."""
        total = len(self._blocks)
        free = len(self._free_blocks)
        return total - free, total
