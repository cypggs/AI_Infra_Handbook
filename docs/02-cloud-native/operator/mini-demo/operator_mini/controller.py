"""Controller —— 把 Source(Informer) → EventHandler → Workqueue → Reconciler 串成流水线。

对应 controller-runtime 的 Controller：它自己不写业务逻辑，只负责"事件入队、出队调用
Reconciler、按 Reconcile 返回值决定重排策略"。step() 是一次完整的"泵事件 + 调和一项"。

run_until_quiescent() 驱动到收敛：循环 step，直到队列空且无待处理事件；遇到延迟项时把
FakeClock 推进到最近的到期时刻（这对应真实集群里"时间自然流逝")。
"""
from .informer import Informer, enqueue_self, enqueue_owner
from .workqueue import RateLimitingQueue, FakeClock
from . import platform
from . import model


class Controller:
    def __init__(self, name, reconciler, clock, max_concurrent=1,
                 base_delay=5.0, max_delay=1000.0):
        self.name = name
        self.reconciler = reconciler
        self.clock = clock
        self.queue = RateLimitingQueue(clock, base_delay, max_delay)
        self.sources = []
        self._platform_state = {}
        self._platform_fn = None
        self.max_concurrent = max_concurrent

        # 可观测性（对应 controller-runtime 的 /metrics）
        self.reconcile_total = 0
        self.reconcile_errors = 0
        self.trace = []        # 人类可读的事件日志

    # ---- 装配 ---- #
    def watch_main(self, apiserver, kind):
        inf = Informer(apiserver, kind, enqueue_self(self.queue))
        self.sources.append(inf)
        return inf

    def watch_owned(self, apiserver, kind, owner_kind):
        inf = Informer(apiserver, kind, enqueue_owner(self.queue, owner_kind))
        self.sources.append(inf)
        return inf

    def attach_platform(self, apiserver, ready_after):
        self._platform_fn = lambda: platform.reconcile_deployments(
            apiserver, self.clock, ready_after, self._platform_state
        )

    def _log(self, msg):
        self.trace.append(msg)

    # ---- 单步 ---- #
    def step(self):
        """一次循环：推进平台 + 泵事件，若有到期项则调和一次。返回是否做了调和。"""
        if self._platform_fn:
            self._platform_fn()
        for inf in self.sources:
            inf.pump()

        key = self.queue.get()
        if key is None:
            return False
        kind, ns, name = key
        self.reconcile_total += 1
        try:
            result, err = self.reconciler.reconcile(kind, ns, name)
        except Exception as e:                       # 防御：异常也走退避重试
            err = e
            result = {}
        self.queue.done(key)

        if err is not None:
            self.reconcile_errors += 1
            self.queue.add_rate_limited(key)         # 指数退避
        elif result.get("requeue_after"):
            self.queue.forget(key)
            self.queue.add_after(key, result["requeue_after"])
        elif result.get("requeue"):
            self.queue.add(key)                      # 立即重排（少用）
        else:
            self.queue.forget(key)                   # 收敛，丢弃
        return True

    # ---- 跑到收敛 ---- #
    def run_until_quiescent(self, max_steps=2000):
        steps = 0
        guard = 0
        while steps < max_steps and guard < max_steps * 6:
            guard += 1
            if self.step():
                steps += 1
                continue
            # 没有到期项可调和
            if self.queue.depth() == 0:
                break
            # 还有延迟项 → 把时钟推进到最近到期时刻（FakeClock）
            nxt = self.queue.next_ready_after()
            if nxt is not None and isinstance(self.clock, FakeClock):
                self.clock.advance(max(0.0, nxt - self.clock.now()))
            else:
                break
        return steps
