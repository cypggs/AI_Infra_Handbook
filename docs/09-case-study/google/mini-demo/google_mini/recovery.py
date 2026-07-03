"""恢复策略：NSDI'24《Resiliency at Scale》的两条真实恢复路径 + 一个裸部署基线。

论文 §5.2-5.3 给出故障后的两条自动化恢复路线（注意：论文里 **没有** "cherry-pick"
一词——本 Demo 的策略名尽量贴合论文术语）：

- **reconfigure（Path 1）**——"reconﬁguring jobs to use spare healthy cubes"：
  OCS 光路重配，把作业从坏 cube 迁到一个空闲的健康 cube，并 **从最近 checkpoint
  恢复**。→ 停机一次（迁移开销），但恢复后 **零持续性能惩罚**；代价是被放弃的坏
  cube 在后台修复期间整片闲置（fleet 代价）。用于机器级 / ICI 链路级故障。
- **reroute（Path 2）**——"fault-tolerant ICI routing"：保留当前分配，libtpunet
  重载 **预计算的容错路由表（wild-first routing）**，让流量绕开坏链路，作业
  **不迁移、不回滚、继续跑**。→ 几乎不停机，但此后每步承受 **持续步时惩罚**
  （论文实测 0.5%–8.6%，多次故障会累积）。用于 blast radius 更大的 OCS 故障，
  也是 95% 作业 opt-in 的默认路径（任意时刻仅 <2% 作业处于该态）。
- **naive**：无自动化韧性的裸部署，故障后等人工 + 物理维修。→ 停机最长。

这正是 NSDI'24 的双轴权衡：**迁移停机（reconfigure）vs 持续步时惩罚（reroute）**。
"""
from dataclasses import dataclass

from .model import JobConfig


@dataclass
class RecoveryOutcome:
    job_downtime_seconds: float        # 该次恢复让作业停机的时间
    fleet_idle_chip_seconds: float     # 该次恢复在集群层面造成的闲置芯片·秒
    rollback: bool                     # True→回滚到最近 checkpoint（naive/reconfigure）；False→原地继续（reroute）
    step_penalty_increment: float      # 此后每步叠加的步时惩罚（仅 reroute > 0）


def apply_strategy(strategy: str, cfg: JobConfig, total_chips: int) -> RecoveryOutcome:
    if strategy == "naive":
        # 无自动化：人工诊断 + 物理维修，停机最长；原地等待，不放弃 cube
        return RecoveryOutcome(
            job_downtime_seconds=cfg.manual_repair_seconds * cfg.naive_downtime_multiplier,
            fleet_idle_chip_seconds=0.0,
            rollback=True,
            step_penalty_increment=0.0,
        )
    if strategy == "reconfigure":
        # Path 1：OCS 重配 + 迁移到空闲健康 cube，从 checkpoint 恢复；
        # 坏 cube 后台修复期间其芯片闲置（fleet 代价）。零持续惩罚。
        return RecoveryOutcome(
            job_downtime_seconds=cfg.ocs_reroute_seconds + cfg.migrate_seconds,
            fleet_idle_chip_seconds=cfg.abandoned_chips * cfg.background_repair_seconds,
            rollback=True,
            step_penalty_increment=0.0,
        )
    if strategy == "reroute":
        # Path 2：保留分配，重载容错 ICI 路由表，不迁移、不回滚；
        # 几乎不停机，但此后每步叠加 cfg.reroute_step_penalty 的步时惩罚（可累积）。
        return RecoveryOutcome(
            job_downtime_seconds=cfg.reroute_seconds,
            fleet_idle_chip_seconds=0.0,
            rollback=False,
            step_penalty_increment=cfg.reroute_step_penalty,
        )
    raise ValueError(f"未知策略: {strategy}")
