"""Entry point demonstrating GPU/CUDA concepts via simulation."""

from gpu_cuda_mini.arch import build_grid, total_threads, warp_count_per_block
from gpu_cuda_mini.kernel import (
    KernelSimulator,
    naive_matmul_transactions,
    tiled_matmul_transactions,
)
from gpu_cuda_mini.memory import GlobalMemory, SharedMemory
from gpu_cuda_mini.occupancy import BlockResourceUsage, occupancy


def demo_warp_and_grid():
    print("=== Warp / Block / Grid layout ===")
    grid = build_grid(grid_dim=(2, 2), block_dim=(4, 4))
    print(f"Grid dim: {grid.grid_dim}, Block dim: {grid.block_dim}")
    print(f"Total threads: {total_threads(grid.grid_dim, grid.block_dim)}")
    block = grid.blocks[0]
    print(f"Threads per block: {len(block.threads)}")
    print(f"Warps per block: {len(block.warps)}")
    for warp in block.warps:
        ids = [t.thread_idx for t in warp.threads]
        print(f"  Warp {warp.warp_id}: {ids}")


def demo_coalescing():
    print("\n=== Global Memory Coalescing ===")
    gm = GlobalMemory(transaction_size=128, element_size=4)
    sim = KernelSimulator(grid_dim=(4,), block_dim=(32,), global_mem=gm)

    def coalesced(t):
        return t.global_idx[0] * 4

    def strided(t):
        return t.global_idx[0] * 4 * 32

    tx_c, addrs_c = sim.simulate_global_access(coalesced)
    tx_s, addrs_s = sim.simulate_global_access(strided)

    print(f"Coalesced access: {tx_c} transactions for {len(addrs_c)} threads")
    print(f"Strided access:   {tx_s} transactions for {len(addrs_s)} threads")
    print(f"Coalescing reduces transactions by {(1 - tx_c / tx_s) * 100:.1f}%")


def demo_bank_conflict():
    print("\n=== Shared Memory Bank Conflict ===")
    sm = SharedMemory(bank_count=32, bank_width=4)
    sim = KernelSimulator(grid_dim=(1,), block_dim=(32,), shared_mem=sm)

    # Row-major access within a 32x32 float array -> different banks.
    def no_conflict(t):
        row = 0
        col = t.thread_idx[0]
        return (row * 32 + col) * 4

    # Column-major access -> all threads hit the same bank.
    def conflict(t):
        row = t.thread_idx[0]
        col = 0
        return (row * 32 + col) * 4

    mc_nc, tc_nc, _ = sim.simulate_shared_access(no_conflict)
    mc_c, tc_c, _ = sim.simulate_shared_access(conflict)

    print(f"Row-major access: max conflict={mc_nc}, total conflicts={tc_nc}")
    print(f"Column-major access: max conflict={mc_c}, total conflicts={tc_c}")


def demo_matmul_tiling():
    print("\n=== Naive vs Tiled MatMul Global Memory Transactions ===")
    N = 64
    gm = GlobalMemory(transaction_size=128, element_size=4)

    naive_a, naive_b, naive_elems = naive_matmul_transactions(N, global_mem=gm)
    naive_total = naive_a + naive_b

    tiled_total, tiled_elems = tiled_matmul_transactions(N, tile_size=8, global_mem=gm)

    print(f"Naive: A={naive_a} tx, B={naive_b} tx, total={naive_total} tx, {naive_elems} element accesses")
    print(f"Tiled: total={tiled_total} tx, {tiled_elems} element accesses")
    print(f"Tiling reduces global transactions by {(1 - tiled_total / naive_total) * 100:.1f}%")


def demo_occupancy():
    print("\n=== Occupancy Calculation ===")
    configs = [
        BlockResourceUsage(threads_per_block=256, registers_per_thread=32, shared_memory_per_block=0),
        BlockResourceUsage(threads_per_block=512, registers_per_thread=64, shared_memory_per_block=0),
        BlockResourceUsage(threads_per_block=256, registers_per_thread=128, shared_memory_per_block=0),
        BlockResourceUsage(threads_per_block=256, registers_per_thread=32, shared_memory_per_block=48 * 1024),
    ]
    for cfg in configs:
        ratio, warps, limit = occupancy(cfg)
        print(
            f"threads={cfg.threads_per_block}, regs/thread={cfg.registers_per_thread}, "
            f"smem={cfg.shared_memory_per_block // 1024}KB -> "
            f"occupancy={ratio:.0%}, active_warps={warps}, limited_by={limit}"
        )


def main():
    demo_warp_and_grid()
    demo_coalescing()
    demo_bank_conflict()
    demo_matmul_tiling()
    demo_occupancy()


if __name__ == "__main__":
    main()
