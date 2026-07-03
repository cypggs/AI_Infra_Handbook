"""Workqueue —— 模拟 client-go RateLimitingQueue：去重 + 延迟重排 + 指数退避。

三条关键语义（对应第 3、5 章讲的工作队列）：

* 去重：同一个 key 短时间内入队多次，只保留一个。level-triggered 抗事件风暴的基础。
* 延迟重排：add_after(key, delay) —— 对应 Reconcile 返回 RequeueAfter（等 Pod ready、周期检查）。
* 指数退避：add_rate_limited(key) —— 失败次数越多退避越久（baseDelay * 2^n，封顶 maxDelay）。

时间用一个可注入的 Clock：演示用 FakeClock（可步进，复现时间线），测试也用 FakeClock。
get() 只返回"已到期"的 key（requeue_at <= now）；未到期的 key 需要时钟推进后才可见。
"""


class Clock:
    def now(self):
        raise NotImplementedError


class RealClock(Clock):
    def now(self):
        import time
        return time.monotonic()


class FakeClock(Clock):
    def __init__(self, t0=0.0):
        self.t = float(t0)

    def now(self):
        return self.t

    def advance(self, dt):
        self.t += float(dt)


class RateLimitingQueue:
    def __init__(self, clock, base_delay=5.0, max_delay=1000.0):
        self.clock = clock
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._pending = {}     # key -> requeue_at（到期时间；== now 表示立即可处理）
        self._order = []       # 立即入队 key 的 FIFO 顺序（保证 get 的可预测性）
        self._failures = {}    # key -> 连续失败次数

    # ---- 入队 ---- #
    def add(self, key):
        """立即入队（去重：已在队列则不重复加）。"""
        if key not in self._pending:
            self._pending[key] = self.clock.now()
            self._order.append(key)

    def add_after(self, key, delay):
        """延迟入队：delay 秒后才可被 get 取出。对应 RequeueAfter。"""
        if key not in self._pending:
            self._pending[key] = self.clock.now() + float(delay)

    def add_rate_limited(self, key):
        """指数退避入队：失败次数 n，退避 base_delay * 2^n（封顶 max_delay）。对应 Reconcile 返回 error。"""
        n = self._failures.get(key, 0)
        delay = min(self.base_delay * (2 ** n), self.max_delay)
        self._failures[key] = n + 1
        if key not in self._pending:
            self._pending[key] = self.clock.now() + delay

    def forget(self, key):
        """重置该 key 的失败计数（成功收敛后调用）。"""
        self._failures.pop(key, None)

    # ---- 出队 ---- #
    def get(self):
        """返回一个已到期的 key；无则 None。不删除（done 才删除）。"""
        now = self.clock.now()
        # 优先按 FIFO 取立即入队项
        for key in list(self._order):
            if key in self._pending and self._pending[key] <= now:
                return key
        # 再扫延迟项
        for key, at in self._pending.items():
            if at <= now:
                return key
        return None

    def done(self, key):
        """标记处理完毕，从队列移除。"""
        self._pending.pop(key, None)
        if key in self._order:
            self._order.remove(key)

    # ---- 观测 ---- #
    def depth(self):
        return len(self._pending)

    def ready_depth(self):
        now = self.clock.now()
        return sum(1 for at in self._pending.values() if at <= now)

    def next_ready_after(self):
        """最早一个未到期 key 的到期时间（用于把 FakeClock 推进到那一刻）。无则 None。"""
        now = self.clock.now()
        future = [at for at in self._pending.values() if at > now]
        return min(future) if future else None

    def failures(self, key):
        return self._failures.get(key, 0)
