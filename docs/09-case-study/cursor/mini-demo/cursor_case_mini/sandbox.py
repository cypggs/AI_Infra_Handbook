"""后台 Agent 沙箱资源配额与调度。

可确证的公开口径：Background/Cloud Agents 在 Cursor 管理的云端隔离
Ubuntu VM 容器中运行（clone 仓库、开分支、交 PR）；Composer 的 RL 训练
复用了同一套 VM 调度器，需要"数十万并发沙箱环境"；2026-09 起支持把
工具执行下沉到客户自有基础设施（Self-Hosted Machines）。

本模块模拟：单台宿主机（CPU/内存配额）上调度一组 Agent 沙箱，
演示 ①配额硬约束 ②空闲回收（scale-to-zero 思路） ③bin-packing 利用率。
完全确定性：不依赖随机数。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QuotaError(Exception):
    reason: str


@dataclass
class Sandbox:
    agent_id: str
    cpu: float  # 核数
    mem_gb: float
    ttl_ticks: int  # 存活周期（tick 数），期间持续占用配额
    started_tick: int = -1


@dataclass
class Host:
    """一台宿主机的沙箱调度器（教学实现：逐 tick 分配 + 空闲回收）。"""

    total_cpu: float = 32.0
    total_mem_gb: float = 128.0
    sandboxes: list[Sandbox] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    def used_cpu(self) -> float:
        return sum(s.cpu for s in self.sandboxes)

    def used_mem(self) -> float:
        return sum(s.mem_gb for s in self.sandboxes)

    def can_fit(self, cpu: float, mem_gb: float) -> bool:
        return self.used_cpu() + cpu <= self.total_cpu + 1e-9 and self.used_mem() + mem_gb <= self.total_mem_gb + 1e-9

    def launch(self, sandbox: Sandbox, tick: int) -> bool:
        """尝试启动沙箱；配额不足返回 False 并记录事件。"""
        if sandbox.cpu <= 0 or sandbox.mem_gb <= 0:
            raise QuotaError("每沙箱 CPU/内存必须为正（隔离配额下限）")
        if not self.can_fit(sandbox.cpu, sandbox.mem_gb):
            self.events.append(f"tick={tick} 排队 agent={sandbox.agent_id} (cpu {sandbox.cpu} mem {sandbox.mem_gb})")
            return False
        sandbox.started_tick = tick
        self.sandboxes.append(sandbox)
        self.events.append(f"tick={tick} 启动 agent={sandbox.agent_id}")
        return True

    def tick(self, tick: int) -> dict[str, int]:
        """推进一个 tick：到期的沙箱回收，返回本 tick 统计。"""
        expired = [s for s in self.sandboxes if tick - s.started_tick >= s.ttl_ticks]
        for s in expired:
            self.sandboxes.remove(s)
            self.events.append(f"tick={tick} 回收 agent={s.agent_id}")
        return {"running": len(self.sandboxes), "cpu_util": round(self.used_cpu() / self.total_cpu, 4)}

    def enforce_quota(self, sandbox: Sandbox, observed_cpu: float, observed_mem_gb: float) -> None:
        """配额强制：任何时刻沙箱观测资源不得超出申请值。"""
        if observed_cpu > sandbox.cpu + 1e-9 or observed_mem_gb > sandbox.mem_gb + 1e-9:
            raise QuotaError(f"agent={sandbox.agent_id} 超出配额: 观测 {observed_cpu}cpu/{observed_mem_gb}g > 申请 {sandbox.cpu}cpu/{sandbox.mem_gb}g")


def run_workload(host: Host, requests: list[Sandbox], n_ticks: int) -> dict[str, float]:
    """跑一个确定性工作负载（请求按序在 tick 0 到达，逐 tick 尝试排队启动）。

    返回：成功启动数、回收数、平均 CPU 利用率、排队失败数。
    """
    queue = list(requests)
    launched = 0
    reclaimed = 0
    utils: list[float] = []
    for tick in range(n_ticks):
        # 先回收到期沙箱
        st = host.tick(tick)
        utils.append(st["cpu_util"])
        # 再尝试启动队列
        still: list[Sandbox] = []
        for sb in queue:
            if host.launch(sb, tick):
                launched += 1
            else:
                still.append(sb)
        queue = still
    reclaimed = sum(1 for e in host.events if "回收" in e)
    failed = sum(1 for e in host.events if "排队" in e)
    return {
        "launched": float(launched),
        "reclaimed": float(reclaimed),
        "queued_events": float(failed),
        "avg_cpu_util": round(float(np_mean(utils)), 4),
        "final_running": float(len(host.sandboxes)),
    }


def np_mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
