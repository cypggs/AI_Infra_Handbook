"""Occupancy simulator for a single SM."""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class SMConstraints:
    """Resource limits for one Streaming Multiprocessor."""

    max_warps_per_sm: int = 32          # Hopper H100 per SM
    max_threads_per_sm: int = 2048      # 64 warps * 32 threads
    max_blocks_per_sm: int = 32
    max_registers_per_sm: int = 65536   # 64K 32-bit registers
    max_shared_memory_per_sm: int = 228 * 1024  # 228 KB Hopper shared/L1
    warp_size: int = 32


@dataclass
class BlockResourceUsage:
    """Resource usage of one thread block."""

    threads_per_block: int
    registers_per_thread: int
    shared_memory_per_block: int


def occupancy(
    block: BlockResourceUsage,
    sm: SMConstraints = None,
) -> Tuple[float, int, str]:
    """Compute theoretical occupancy for a block on a given SM.

    Returns:
        (occupancy_ratio, active_warps, limiting_factor)
    """
    sm = sm or SMConstraints()
    warps_per_block = (block.threads_per_block + sm.warp_size - 1) // sm.warp_size

    # Limit by warps
    max_blocks_by_warps = sm.max_warps_per_sm // warps_per_block
    # Limit by threads
    max_blocks_by_threads = sm.max_threads_per_sm // block.threads_per_block
    # Limit by registers
    total_registers = block.threads_per_block * block.registers_per_thread
    max_blocks_by_registers = sm.max_registers_per_sm // total_registers
    # Limit by shared memory
    max_blocks_by_shared = (
        sm.max_shared_memory_per_sm // block.shared_memory_per_block
        if block.shared_memory_per_block > 0 else sm.max_blocks_per_sm
    )
    # Limit by blocks
    max_blocks_by_blocks = sm.max_blocks_per_sm

    active_blocks = min(
        max_blocks_by_warps,
        max_blocks_by_threads,
        max_blocks_by_registers,
        max_blocks_by_shared,
        max_blocks_by_blocks,
    )
    active_warps = active_blocks * warps_per_block
    occupancy_ratio = active_warps / sm.max_warps_per_sm

    limits = {
        "warps": max_blocks_by_warps,
        "threads": max_blocks_by_threads,
        "registers": max_blocks_by_registers,
        "shared_memory": max_blocks_by_shared,
        "blocks": max_blocks_by_blocks,
    }
    limiting_factor = min(limits, key=limits.get)

    return occupancy_ratio, active_warps, limiting_factor
