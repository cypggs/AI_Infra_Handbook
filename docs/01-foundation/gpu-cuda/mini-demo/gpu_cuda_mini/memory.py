"""Memory model simulation: global memory coalescing and shared memory bank conflict."""

from typing import Callable, List, Set, Tuple


class GlobalMemory:
    """Simulate global memory with cache-line based transactions."""

    def __init__(self, transaction_size: int = 128, element_size: int = 4):
        """
        Args:
            transaction_size: Size of a cache line / memory transaction in bytes.
            element_size: Size of each accessed element in bytes.
        """
        self.transaction_size = transaction_size
        self.element_size = element_size

    def transactions(self, addresses: List[int]) -> int:
        """Count how many cache-line transactions are needed for a list of addresses."""
        lines: Set[int] = set()
        for addr in addresses:
            lines.add(addr // self.transaction_size)
        return len(lines)

    def addresses_for_row_major(
        self, base: int, indices: List[int]
    ) -> List[int]:
        """Compute byte addresses for row-major contiguous access."""
        return [base + idx * self.element_size for idx in indices]

    def addresses_for_strided(
        self, base: int, indices: List[int], stride: int
    ) -> List[int]:
        """Compute byte addresses for strided access (e.g. column-major)."""
        return [base + idx * stride * self.element_size for idx in indices]


class SharedMemory:
    """Simulate shared memory bank layout."""

    def __init__(self, bank_count: int = 32, bank_width: int = 4):
        """
        Args:
            bank_count: Number of banks (NVIDIA modern GPUs use 32).
            bank_width: Width of each bank in bytes (4 bytes for 32-bit floats).
        """
        self.bank_count = bank_count
        self.bank_width = bank_width

    def bank(self, address: int) -> int:
        """Return the bank index for a byte address."""
        return (address // self.bank_width) % self.bank_count

    def detect_conflict(self, addresses: List[int]) -> Tuple[int, int]:
        """Detect bank conflicts for a list of addresses accessed simultaneously.

        Returns:
            (max_conflict, total_conflicts):
            - max_conflict: maximum number of threads hitting the same bank.
            - total_conflicts: sum of (threads_per_bank - 1) across all banks.
        """
        from collections import Counter

        banks = [self.bank(a) for a in addresses]
        counts = Counter(banks)
        max_conflict = max(counts.values()) if counts else 0
        total_conflicts = sum(c - 1 for c in counts.values())
        return max_conflict, total_conflicts
