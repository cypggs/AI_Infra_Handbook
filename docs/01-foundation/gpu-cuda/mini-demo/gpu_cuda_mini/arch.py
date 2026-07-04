"""Minimal GPU architecture simulation.

This module models the GPU execution hierarchy (Grid / Block / Warp / Thread)
without any real GPU hardware. It is used for educational purposes only.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Thread:
    """A single CUDA thread."""

    block_idx: Tuple[int, ...]
    thread_idx: Tuple[int, ...]
    global_idx: Tuple[int, ...]


@dataclass(frozen=True)
class Warp:
    """A warp is a group of 32 threads scheduled together."""

    warp_id: int
    block_idx: Tuple[int, ...]
    threads: List[Thread]


@dataclass
class ThreadBlock:
    """A CUDA thread block, split into warps."""

    block_idx: Tuple[int, ...]
    block_dim: Tuple[int, ...]
    threads: List[Thread]
    warps: List[Warp]


@dataclass
class Grid:
    """A CUDA grid, composed of thread blocks."""

    grid_dim: Tuple[int, ...]
    block_dim: Tuple[int, ...]
    blocks: List[ThreadBlock]


def _linear_index(idx: Tuple[int, ...], dim: Tuple[int, ...]) -> int:
    """Convert multi-dimensional index to linear row-major index."""
    total = 0
    stride = 1
    for i, d in zip(reversed(idx), reversed(dim)):
        total += i * stride
        stride *= d
    return total


def build_grid(grid_dim: Tuple[int, ...], block_dim: Tuple[int, ...]) -> Grid:
    """Build a simulated Grid/Block/Thread hierarchy.

    Args:
        grid_dim: Number of blocks in each dimension.
        block_dim: Number of threads per block in each dimension.

    Returns:
        A Grid object containing all blocks, threads and warps.
    """
    if len(grid_dim) != len(block_dim):
        raise ValueError("grid_dim and block_dim must have same length")

    warp_size = 32
    blocks: List[ThreadBlock] = []

    def iter_indices(dim: Tuple[int, ...]):
        if not dim:
            yield ()
            return
        if len(dim) == 1:
            for i in range(dim[0]):
                yield (i,)
            return
        for i in range(dim[0]):
            for rest in iter_indices(dim[1:]):
                yield (i,) + rest

    for bidx in iter_indices(grid_dim):
        threads: List[Thread] = []
        for tidx in iter_indices(block_dim):
            gidx = tuple(
                bidx[i] * block_dim[i] + tidx[i] for i in range(len(grid_dim))
            )
            threads.append(Thread(block_idx=bidx, thread_idx=tidx, global_idx=gidx))

        # Split threads into warps in row-major order (same as NVIDIA hardware).
        warps: List[Warp] = []
        for w in range((len(threads) + warp_size - 1) // warp_size):
            start = w * warp_size
            end = min(start + warp_size, len(threads))
            warps.append(
                Warp(
                    warp_id=w,
                    block_idx=bidx,
                    threads=threads[start:end],
                )
            )

        blocks.append(ThreadBlock(block_idx=bidx, block_dim=block_dim, threads=threads, warps=warps))

    return Grid(grid_dim=grid_dim, block_dim=block_dim, blocks=blocks)


def warp_count_per_block(block_dim: Tuple[int, ...]) -> int:
    """Return number of warps in a block with the given dimensions."""
    total_threads = 1
    for d in block_dim:
        total_threads *= d
    return (total_threads + 31) // 32


def total_threads(grid_dim: Tuple[int, ...], block_dim: Tuple[int, ...]) -> int:
    """Return total number of threads launched by a kernel."""
    g = 1
    b = 1
    for d in grid_dim:
        g *= d
    for d in block_dim:
        b *= d
    return g * b
