"""时钟抽象：真实墙钟 + 可控假钟。

FakeClock 让我们能精确控制 step 时长、复现调度时间线。
"""
from __future__ import annotations

import time


class Clock:
    """时钟基类。"""

    def now(self) -> float:
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        raise NotImplementedError


class RealClock(Clock):
    """真实墙钟。"""

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class FakeClock(Clock):
    """可控假钟：时间只能被显式推进。

    用于确定性测试 —— 每个操作调用 advance() 推进指定秒数，
    就能精确断言"rollout 用时 1.24s"之类的指标。
    """

    def __init__(self, start: float = 0.0):
        self._t = start

    def now(self) -> float:
        return self._t

    def sleep(self, seconds: float) -> None:
        self._t += seconds

    def advance(self, seconds: float) -> float:
        self._t += seconds
        return self._t
