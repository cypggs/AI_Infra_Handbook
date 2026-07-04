from gpu_cuda_mini.arch import build_grid
from gpu_cuda_mini.kernel import KernelSimulator
from gpu_cuda_mini.memory import GlobalMemory, SharedMemory


def test_coalesced_vs_strided():
    gm = GlobalMemory(transaction_size=128, element_size=4)
    sim = KernelSimulator(grid_dim=(4,), block_dim=(32,), global_mem=gm)

    def coalesced(t):
        return t.global_idx[0] * 4

    def strided(t):
        return t.global_idx[0] * 4 * 32

    tx_c, _ = sim.simulate_global_access(coalesced)
    tx_s, _ = sim.simulate_global_access(strided)
    assert tx_c < tx_s
    assert tx_c == 4  # 128 threads, 32 per warp, 1 tx per warp = 4
    assert tx_s == 128  # each thread in its own cache line


def test_shared_bank_conflict():
    sm = SharedMemory(bank_count=32, bank_width=4)
    sim = KernelSimulator(grid_dim=(1,), block_dim=(32,), shared_mem=sm)

    def no_conflict(t):
        return (0 * 32 + t.thread_idx[0]) * 4

    def conflict(t):
        return (t.thread_idx[0] * 32 + 0) * 4

    mc_nc, tc_nc, _ = sim.simulate_shared_access(no_conflict)
    mc_c, tc_c, _ = sim.simulate_shared_access(conflict)

    assert mc_nc == 1 and tc_nc == 0
    assert mc_c == 32 and tc_c == 31


def test_bank_function():
    sm = SharedMemory()
    assert sm.bank(0) == 0
    assert sm.bank(4) == 1
    assert sm.bank(128) == 0
