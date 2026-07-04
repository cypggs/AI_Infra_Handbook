"""Block device simulator."""

from typing import List, Optional


class BlockDevice:
    """A simple block device backed by memory.

    Simulates fixed-size blocks, an allocation bitmap, and bad-block marking.
    """

    def __init__(self, num_blocks: int, block_size: int = 4096):
        if num_blocks <= 0 or block_size <= 0:
            raise ValueError("num_blocks and block_size must be positive")
        self.num_blocks = num_blocks
        self.block_size = block_size
        self._data: List[bytes] = [b"" for _ in range(num_blocks)]
        self._allocated: List[bool] = [False] * num_blocks
        self._bad: List[bool] = [False] * num_blocks

    def allocate(self) -> int:
        """Allocate the first free good block. Returns block id or raises RuntimeError."""
        for bid in range(self.num_blocks):
            if not self._allocated[bid] and not self._bad[bid]:
                self._allocated[bid] = True
                self._data[bid] = b"\x00" * self.block_size
                return bid
        raise RuntimeError("no free block available")

    def free(self, bid: int) -> None:
        self._validate_index(bid)
        self._allocated[bid] = False
        self._data[bid] = b""

    def read_block(self, bid: int) -> bytes:
        self._validate_index(bid)
        if self._bad[bid]:
            raise OSError(f"block {bid} is bad")
        if not self._allocated[bid]:
            return b"\x00" * self.block_size
        return self._data[bid]

    def write_block(self, bid: int, data: bytes) -> None:
        self._validate_index(bid)
        if self._bad[bid]:
            raise OSError(f"block {bid} is bad")
        if len(data) > self.block_size:
            raise ValueError(f"data exceeds block size {self.block_size}")
        if not self._allocated[bid]:
            self._allocated[bid] = True
        self._data[bid] = data.ljust(self.block_size, b"\x00")

    def mark_bad(self, bid: int) -> None:
        self._validate_index(bid)
        self._bad[bid] = True
        self._allocated[bid] = False
        self._data[bid] = b""

    def is_bad(self, bid: int) -> bool:
        self._validate_index(bid)
        return self._bad[bid]

    def allocated_count(self) -> int:
        return sum(self._allocated)

    def free_count(self) -> int:
        return self.num_blocks - self.allocated_count()

    def _validate_index(self, bid: int) -> None:
        if not (0 <= bid < self.num_blocks):
            raise IndexError(f"block id {bid} out of range")
