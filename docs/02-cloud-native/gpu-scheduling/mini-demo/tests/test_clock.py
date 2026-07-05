"""clock.py 测试。"""
import pytest

from gpu_scheduling_mini.clock import FakeClock, RealClock


def test_fake_clock_starts_at_zero():
    c = FakeClock()
    assert c.now() == 0.0


def test_fake_clock_advances():
    c = FakeClock(t0=10.0)
    c.advance(2.5)
    assert c.now() == 12.5


def test_real_clock_increases():
    c = RealClock()
    t0 = c.now()
    # 极小概率在测试执行瞬间时间倒流；这里只是验证单调性
    assert c.now() >= t0
