"""离散事件时钟：为异构调度与流式加载提供确定性的时间线语义。

真实系统里这些是 OS 调度器、硬件计时器与 DMA 引擎的组合行为；这里用一个
可步进的伪时钟把「谁先谁后、各自花了多久」变成可测试的纯函数关系。
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Callable, List, Tuple


@dataclass(order=True)
class Event:
    """一个计划在 ``at_us`` 微秒触发的事件。"""

    at_us: float
    seq: int
    name: str = field(compare=False, default="")
    callback: Callable[[], None] = field(compare=False, default=lambda: None)


class FakeClock:
    """单调递增的伪时钟 + 最小堆事件队列。

    用法::

        clock = FakeClock()
        clock.schedule(100.0, "op_done", fn)
        clock.run()            # 按时间顺序触发所有事件
        assert clock.now_us == 100.0
    """

    def __init__(self, start_us: float = 0.0) -> None:
        self._now_us = float(start_us)
        self._seq = 0
        self._queue: List[Event] = []
        self.history: List[Tuple[float, str]] = []

    @property
    def now_us(self) -> float:
        return self._now_us

    def advance(self, delta_us: float) -> None:
        if delta_us < 0:
            raise ValueError("clock cannot go backwards")
        self._now_us += float(delta_us)

    def schedule(self, at_us: float, name: str, callback: Callable[[], None] = lambda: None) -> None:
        if at_us < self._now_us:
            raise ValueError("cannot schedule an event in the past")
        self._seq += 1
        heapq.heappush(self._queue, Event(float(at_us), self._seq, name, callback))

    def schedule_after(self, delay_us: float, name: str, callback: Callable[[], None] = lambda: None) -> None:
        self.schedule(self._now_us + float(delay_us), name, callback)

    def run(self) -> None:
        """触发队列中所有事件（按时间顺序，同时刻按入队顺序）。"""
        while self._queue:
            ev = heapq.heappop(self._queue)
            if ev.at_us < self._now_us:
                raise ValueError("event scheduled in the past")
            self._now_us = ev.at_us
            self.history.append((ev.at_us, ev.name))
            ev.callback()

    def pending(self) -> int:
        return len(self._queue)
