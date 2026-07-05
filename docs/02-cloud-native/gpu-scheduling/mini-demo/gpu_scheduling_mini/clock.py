"""Clock —— 可注入时间源：教学演示用 FakeClock，测试也全部用 FakeClock。

真实组件里由 kubelet / scheduler / device-plugin 自己读取 wall-clock；
本模拟器为了单线程、确定性、可精确复现时间线，把时间抽象成 Clock.now()。"""


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
