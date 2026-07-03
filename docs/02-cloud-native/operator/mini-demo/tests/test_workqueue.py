"""Workqueue 测试：去重、延迟重排、指数退避、forget、到期可见性。"""
from operator_mini.workqueue import RateLimitingQueue, FakeClock


def test_add_is_immediate():
    q = RateLimitingQueue(FakeClock())
    q.add("a")
    assert q.get() == "a"


def test_dedup():
    q = RateLimitingQueue(FakeClock())
    q.add("a")
    q.add("a")
    assert q.depth() == 1


def test_add_after_delays_visibility():
    clk = FakeClock()
    q = RateLimitingQueue(clk)
    q.add_after("a", 5.0)
    assert q.get() is None, "未到期不应可见"
    clk.advance(5.0)
    assert q.get() == "a"


def test_exponential_backoff():
    clk = FakeClock()
    q = RateLimitingQueue(clk, base_delay=5.0, max_delay=1000.0)
    q.add_rate_limited("a")   # 第 0 次失败 → 5s
    assert clk.now() == 0.0
    q.done("a")
    q.add_rate_limited("a")   # 第 1 次 → 10s
    assert q.next_ready_after() == 10.0
    q.done("a")
    q.add_rate_limited("a")   # 第 2 次 → 20s
    clk.advance(15.0)
    assert q.get() is None, "20s 才到期，15s 还不可见"
    clk.advance(5.0)
    assert q.get() == "a"


def test_backoff_caps_at_max():
    clk = FakeClock()
    q = RateLimitingQueue(clk, base_delay=5.0, max_delay=100.0)
    for i in range(20):
        q.add_rate_limited("a")
        if i < 19:          # 最后一次不 done，保留在队列里以便观测到期时间
            q.done("a")
    assert q.next_ready_after() == 100.0  # 不超过 max_delay


def test_forget_resets_failures():
    clk = FakeClock()
    q = RateLimitingQueue(clk, base_delay=5.0)
    q.add_rate_limited("a"); q.done("a")
    q.add_rate_limited("a"); q.done("a")
    assert q.failures("a") == 2
    q.forget("a")
    assert q.failures("a") == 0
    q.add_rate_limited("a")
    assert q.next_ready_after() == 5.0   # 退避重置


def test_done_removes_item():
    q = RateLimitingQueue(FakeClock())
    q.add("a")
    q.get()
    q.done("a")
    assert q.depth() == 0
    assert q.get() is None


def test_ready_depth():
    clk = FakeClock()
    q = RateLimitingQueue(clk)
    q.add("a")
    q.add_after("b", 10.0)
    assert q.ready_depth() == 1
    assert q.depth() == 2
