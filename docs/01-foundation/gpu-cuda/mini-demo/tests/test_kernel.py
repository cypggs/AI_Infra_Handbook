from gpu_cuda_mini.kernel import naive_matmul_transactions, tiled_matmul_transactions
from gpu_cuda_mini.memory import GlobalMemory


def test_tiled_reduces_transactions():
    N = 64
    gm = GlobalMemory(transaction_size=128, element_size=4)
    naive_a, naive_b, _ = naive_matmul_transactions(N, global_mem=gm)
    naive_total = naive_a + naive_b
    tiled_total, _ = tiled_matmul_transactions(N, tile_size=8, global_mem=gm)
    assert tiled_total < naive_total


def test_larger_tile_fewer_transactions():
    N = 64
    gm = GlobalMemory(transaction_size=128, element_size=4)
    t4, _ = tiled_matmul_transactions(N, tile_size=4, global_mem=gm)
    t8, _ = tiled_matmul_transactions(N, tile_size=8, global_mem=gm)
    assert t8 <= t4
