"""Cgroup：资源限制 + 计量（cpu / memory / pids），含 CFS throttle 与 OOM 行为。

对应 Linux cgroup v2 的 cpu.max / memory.max / pids.max 控制器：
- cpu.max = (quota, period)：每 period 微秒可用 quota 微秒 CPU；超出则 throttle（节流）。
  对应 K8s resources.limits.cpu（硬上限）。K8s v1.x 后 cpu request 对应 cpu.weight。
- memory.max：硬上限；超出则 OOM Killer 杀掉该 cgroup 内存最大的进程（OOMKilled）。
  对应 K8s resources.limits.memory。
- pids.max：进程数上限，防 fork bomb。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Cgroup:
    name: str
    # 限制（-1 / max 表示不限）
    cpu_quota_us: int = -1
    cpu_period_us: int = 100_000
    memory_max: int = -1  # bytes
    pids_max: int = -1
    # 计量
    memory_current: int = 0
    cpu_used_us: int = 0
    nr_periods: int = 0
    nr_throttled: int = 0
    throttled_usec: int = 0
    nr_pids: int = 0
    oom_kills: int = 0

    @property
    def cpu_max(self) -> str:
        return "max" if self.cpu_quota_us < 0 else f"{self.cpu_quota_us} {self.cpu_period_us}"

    def tick(self, cpu_used_us: int) -> str:
        """记账一个 CFS 周期的 CPU 使用。返回 'ok' 或 'throttled'。"""
        self.nr_periods += 1
        if self.cpu_quota_us > 0:
            if cpu_used_us > self.cpu_quota_us:
                self.nr_throttled += 1
                self.throttled_usec += cpu_used_us - self.cpu_quota_us
                self.cpu_used_us += self.cpu_quota_us  # 只有 quota 这部分真正执行了
                return "throttled"
        self.cpu_used_us += cpu_used_us
        return "ok"

    def consume_memory(self, bytes_: int) -> str:
        """分配内存。返回 'ok' 或 'oom'（超出 memory.max 被拒）。"""
        self.memory_current += bytes_
        if self.memory_max > 0 and self.memory_current > self.memory_max:
            self.oom_kills += 1
            self.memory_current -= bytes_  # OOM：分配被拒，回滚
            return "oom"
        return "ok"

    def release_memory(self, bytes_: int) -> None:
        self.memory_current = max(0, self.memory_current - bytes_)

    def acquire_pid(self) -> str:
        """fork 一个进程。返回 'ok' 或 'pids-exceeded'（超出 pids.max）。"""
        if self.pids_max > 0 and self.nr_pids >= self.pids_max:
            return "pids-exceeded"
        self.nr_pids += 1
        return "ok"

    def stat(self) -> dict:
        return {
            "cpu.max": self.cpu_max,
            "cpu_used_us": self.cpu_used_us,
            "nr_periods": self.nr_periods,
            "nr_throttled": self.nr_throttled,
            "throttled_usec": self.throttled_usec,
            "memory.current": self.memory_current,
            "memory.max": self.memory_max if self.memory_max > 0 else "max",
            "pids.current": self.nr_pids,
            "oom_kills": self.oom_kills,
        }
