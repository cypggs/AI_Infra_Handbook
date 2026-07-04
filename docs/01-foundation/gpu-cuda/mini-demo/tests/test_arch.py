from gpu_cuda_mini.arch import build_grid, total_threads, warp_count_per_block


def test_grid_dimensions():
    grid = build_grid(grid_dim=(2, 3), block_dim=(4, 8))
    assert len(grid.blocks) == 6
    assert len(grid.blocks[0].threads) == 32
    assert len(grid.blocks[0].warps) == 1


def test_warp_count():
    assert warp_count_per_block((32,)) == 1
    assert warp_count_per_block((128,)) == 4
    assert warp_count_per_block((256,)) == 8
    assert warp_count_per_block((16, 16)) == 8


def test_total_threads():
    assert total_threads((2, 2), (4, 4)) == 64
    assert total_threads((2, 2, 2), (4, 4, 4)) == 512
    assert total_threads((10,), (256,)) == 2560
