"""FakeClock 的确定性语义测试。"""

import pytest

from edge_inference_mini.clock import FakeClock


def test_initial_time():
    assert FakeClock().now_us == 0.0
    assert FakeClock(start_us=100.0).now_us == 100.0


def test_advance_monotonic():
    c = FakeClock()
    c.advance(50.0)
    c.advance(25.5)
    assert c.now_us == 75.5


def test_advance_negative_rejected():
    c = FakeClock()
    with pytest.raises(ValueError):
        c.advance(-1.0)


def test_schedule_in_past_rejected():
    c = FakeClock()
    c.advance(10.0)
    with pytest.raises(ValueError):
        c.schedule(5.0, "bad")


def test_events_run_in_time_order():
    c = FakeClock()
    order = []
    c.schedule(30.0, "b", lambda: order.append("b"))
    c.schedule(10.0, "a", lambda: order.append("a"))
    c.schedule(20.0, "c", lambda: order.append("c"))
    c.run()
    assert order == ["a", "c", "b"]
    assert c.now_us == 30.0


def test_same_time_fifo():
    c = FakeClock()
    order = []
    c.schedule(10.0, "first", lambda: order.append(1))
    c.schedule(10.0, "second", lambda: order.append(2))
    c.run()
    assert order == [1, 2]


def test_schedule_after_relative():
    c = FakeClock()
    c.advance(100.0)
    c.schedule_after(40.0, "x")
    assert c.pending() == 1
    c.run()
    assert c.now_us == 140.0
    assert c.history == [(140.0, "x")]
