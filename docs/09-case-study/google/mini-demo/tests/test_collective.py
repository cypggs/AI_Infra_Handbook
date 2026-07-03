from google_mini.collective import (
    latency_term,
    ring_allreduce_time,
    single_ring_time,
    torus_allreduce_time,
)


def test_ring_allreduce_single_node_is_zero():
    assert ring_allreduce_time(1, 1024, 1e9, 1e-6) == 0.0


def test_ring_allreduce_grows_with_ring_len():
    msg, bw, lat = 1 << 20, 1e9, 1e-6
    assert ring_allreduce_time(4, msg, bw, lat) > ring_allreduce_time(2, msg, bw, lat)


def test_latency_term_formula():
    # 2·Σ(d-1)
    assert latency_term((4, 4, 4)) == 2 * (3 + 3 + 3)
    assert latency_term((16, 16, 16)) == 2 * (15 + 15 + 15)  # 90


def test_torus_latency_term_is_the_structural_win():
    """核心洞察：torus 分维延迟项 2·Σ(d-1) 远低于单环 2·(N-1)。"""
    dims = (16, 16, 16)
    n = 16 ** 3
    assert latency_term(dims) == 90
    assert 2 * (n - 1) == 8190
    # 延迟项约为单环的 1%
    assert latency_term(dims) < 0.02 * (2 * (n - 1))


def test_torus_total_time_regimes():
    """带宽主导（大消息）下 torus 仍更快；延迟主导（小消息）下优势放大到 ~1%。"""
    dims = (16, 16, 16)
    n = 16 ** 3
    bw, lat = 50.0e9, 1.0e-6
    # 大消息：带宽主导，torus 省下 ~8ms 延迟差，总时间仍更低
    big = 512 * 1024 * 1024
    assert torus_allreduce_time(dims, big, bw, lat) < single_ring_time(n, big, bw, lat)
    # 小消息：延迟主导，torus 总时间 < 单环的 5%
    small = 1024
    assert torus_allreduce_time(dims, small, bw, lat) < 0.05 * single_ring_time(n, small, bw, lat)


def test_torus_matches_decomposition():
    """手动按分维公式核算 4×4×4 上的 AllReduce 时间。"""
    msg, bw, lat = 512 * 1024 * 1024, 50.0e9, 1.0e-6
    expected = 0.0
    shard = 1
    for d in (4, 4, 4):
        step_bytes = msg / (shard * d)
        expected += 2.0 * (d - 1) * (lat + step_bytes / bw)
        shard *= d
    assert abs(torus_allreduce_time((4, 4, 4), msg, bw, lat) - expected) < 1e-12
