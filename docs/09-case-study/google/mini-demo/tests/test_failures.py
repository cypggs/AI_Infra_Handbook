import random

from google_mini.failures import per_step_cluster_hazard, roll_failures, sample_failure


def test_hazard_formula_single_step():
    # 单芯片一步内故障概率 = rate * step/3600
    rate, n, step = 2.0e-3, 1, 3.6  # 3.6s 一步
    expected = 1.0 - (1.0 - rate * (step / 3600.0)) ** 1
    assert abs(per_step_cluster_hazard(rate, n, step) - expected) < 1e-15


def test_hazard_grows_with_cluster_size():
    rate, step = 1.0e-3, 1.0
    h64 = per_step_cluster_hazard(rate, 64, step)
    h4096 = per_step_cluster_hazard(rate, 4096, step)
    assert h4096 > h64
    # size 在指数上：4096 倍芯片 → hazard 接近线性放大（小概率近似）
    assert h4096 / h64 > 50.0


def test_hazard_zero_rate_is_zero():
    assert per_step_cluster_hazard(0.0, 4096, 1.0) == 0.0


def test_sample_failure_deterministic_and_bounded():
    rng = random.Random(42)
    draws = [sample_failure(rng, 0.5) for _ in range(100)]
    # 相同 seed 可复现
    rng2 = random.Random(42)
    draws2 = [sample_failure(rng2, 0.5) for _ in range(100)]
    assert draws == draws2
    # hazard=0 永不触发，hazard=1 必触发
    assert all(not sample_failure(random.Random(i), 0.0) for i in range(10))
    assert all(sample_failure(random.Random(i), 1.0) for i in range(10))


def test_roll_failures_length_and_determinism():
    rng = random.Random(7)
    seq = roll_failures(rng, 50, 0.5)
    assert len(seq) == 50
    assert all(isinstance(x, bool) for x in seq)
    # 相同 seed 可复现
    assert roll_failures(random.Random(7), 50, 0.5) == seq


def test_roll_failures_hazard_extremes():
    assert not any(roll_failures(random.Random(1), 20, 0.0))   # hazard=0 → 全 False
    assert all(roll_failures(random.Random(1), 20, 1.0))       # hazard=1 → 全 True
