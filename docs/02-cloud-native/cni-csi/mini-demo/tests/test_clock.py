"""clock.py 测试。"""
import time

from cni_csi_mini.clock import FakeClock, RealClock


def test_fake_clock_advances():
    clock = FakeClock(10.0)
    assert clock.now() == 10.0
    clock.advance(5.0)
    assert clock.now() == 15.0


def test_real_clock_is_monotonic():
    clock = RealClock()
    before = clock.now()
    time.sleep(0.001)
    after = clock.now()
    assert after >= before
