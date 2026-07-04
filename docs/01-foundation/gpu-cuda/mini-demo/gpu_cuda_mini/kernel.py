"""Simulate simple CUDA kernels to demonstrate coalescing, tiling and divergence."""

from typing import Callable, List, Tuple

from .arch import Thread, ThreadBlock, Warp, build_grid
from .memory import GlobalMemory, SharedMemory


class KernelSimulator:
    """Simulate execution of a kernel and collect memory statistics."""

    def __init__(
        self,
        grid_dim: Tuple[int, ...],
        block_dim: Tuple[int, ...],
        global_mem: GlobalMemory = None,
        shared_mem: SharedMemory = None,
    ):
        self.grid = build_grid(grid_dim, block_dim)
        self.global_mem = global_mem or GlobalMemory()
        self.shared_mem = shared_mem or SharedMemory()

    def simulate_global_access(
        self, access_fn: Callable[[Thread], int]
    ) -> Tuple[int, List[int]]:
        """Simulate a kernel where each thread accesses one global address.

        Transactions are counted per warp, matching real GPU behavior: each warp
        that needs a cache line issues a separate transaction.

        Returns:
            (transaction_count, list_of_addresses)
        """
        addresses: List[int] = []
        transactions = 0
        for block in self.grid.blocks:
            for warp in block.warps:
                warp_addrs = [access_fn(t) for t in warp.threads]
                addresses.extend(warp_addrs)
                transactions += self.global_mem.transactions(warp_addrs)
        return transactions, addresses

    def simulate_shared_access(
        self, access_fn: Callable[[Thread], int]
    ) -> Tuple[int, int, List[int]]:
        """Simulate shared memory access per warp and detect bank conflicts.

        Returns:
            (max_conflict, total_conflicts, all_addresses)
        """
        all_addresses: List[int] = []
        max_conflict = 0
        total_conflicts = 0
        for block in self.grid.blocks:
            for warp in block.warps:
                addresses = [access_fn(t) for t in warp.threads]
                all_addresses.extend(addresses)
                mc, tc = self.shared_mem.detect_conflict(addresses)
                max_conflict = max(max_conflict, mc)
                total_conflicts += tc
        return max_conflict, total_conflicts, all_addresses


def naive_matmul_transactions(
    N: int,
    global_mem: GlobalMemory = None,
) -> Tuple[int, int, int]:
    """Simulate naive row-column matrix multiplication global memory transactions.

    Each thread computes one element of C. A is read row-major (coalesced),
    B is read column-major (strided). Returns (a_transactions, b_transactions,
    total_element_accesses).
    """
    gm = global_mem or GlobalMemory()
    element_size = gm.element_size

    sim = KernelSimulator(grid_dim=(N, N), block_dim=(1, 1), global_mem=gm)

    a_base = 0
    b_base = N * N * element_size

    a_transactions = 0
    b_transactions = 0
    element_accesses = 0

    # Each thread (row, col) reads an entire row of A and column of B.
    for block in sim.grid.blocks:
        for warp in block.warps:
            a_warp_addrs: List[int] = []
            b_warp_addrs: List[int] = []
            for thread in warp.threads:
                row = thread.global_idx[1]
                col = thread.global_idx[0]
                for k in range(N):
                    a_warp_addrs.append(a_base + (row * N + k) * element_size)
                    b_warp_addrs.append(b_base + (k * N + col) * element_size)
                    element_accesses += 2
            a_transactions += gm.transactions(a_warp_addrs)
            b_transactions += gm.transactions(b_warp_addrs)

    return a_transactions, b_transactions, element_accesses


def tiled_matmul_transactions(
    N: int,
    tile_size: int,
    global_mem: GlobalMemory = None,
) -> Tuple[int, int]:
    """Simulate tiled matrix multiplication global memory transactions.

    A block of threads collaboratively loads tiles of A and B into shared memory,
    then reuses them across the tile. Global memory reads happen once per tile
    element per block, not once per output element.

    Returns (global_transactions, element_accesses).
    """
    gm = global_mem or GlobalMemory()
    element_size = gm.element_size

    if N % tile_size != 0:
        raise ValueError("N must be divisible by tile_size")

    tiles_per_dim = N // tile_size
    sim = KernelSimulator(
        grid_dim=(tiles_per_dim, tiles_per_dim),
        block_dim=(tile_size, tile_size),
        global_mem=gm,
    )

    a_base = 0
    b_base = N * N * element_size

    total_transactions = 0
    element_accesses = 0

    for block in sim.grid.blocks:
        block_row = block.block_idx[1]
        block_col = block.block_idx[0]
        for k_tile in range(tiles_per_dim):
            # Each thread loads one element of the A tile and one of the B tile.
            a_warp_addrs: List[int] = []
            b_warp_addrs: List[int] = []
            for warp in block.warps:
                for thread in warp.threads:
                    tx = thread.thread_idx[0]
                    ty = thread.thread_idx[1]
                    row_a = block_row * tile_size + ty
                    col_a = k_tile * tile_size + tx
                    a_warp_addrs.append(a_base + (row_a * N + col_a) * element_size)
                    row_b = k_tile * tile_size + ty
                    col_b = block_col * tile_size + tx
                    b_warp_addrs.append(b_base + (row_b * N + col_b) * element_size)
                    element_accesses += 2
            total_transactions += gm.transactions(a_warp_addrs)
            total_transactions += gm.transactions(b_warp_addrs)

    return total_transactions, element_accesses
