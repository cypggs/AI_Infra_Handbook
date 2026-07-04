from gpu_cuda_mini.occupancy import BlockResourceUsage, occupancy


def test_occupancy_basic():
    cfg = BlockResourceUsage(threads_per_block=256, registers_per_thread=32, shared_memory_per_block=0)
    ratio, warps, limit = occupancy(cfg)
    assert ratio == 1.0
    assert warps == 32
    assert limit == "warps" or limit == "blocks"


def test_register_limited():
    cfg = BlockResourceUsage(threads_per_block=512, registers_per_thread=128, shared_memory_per_block=0)
    ratio, warps, limit = occupancy(cfg)
    assert limit == "registers"
    assert ratio < 1.0


def test_shared_memory_limited():
    cfg = BlockResourceUsage(
        threads_per_block=256, registers_per_thread=32, shared_memory_per_block=120 * 1024
    )
    ratio, warps, limit = occupancy(cfg)
    assert limit == "shared_memory"
    assert ratio <= 1.0
