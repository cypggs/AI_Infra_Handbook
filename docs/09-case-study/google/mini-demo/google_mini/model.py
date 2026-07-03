"""数据结构：模拟配置与结果。"""
from dataclasses import dataclass
from typing import Tuple


@dataclass
class JobConfig:
    """一次 3D-torus 同步训练模拟的配置。"""

    # --- 拓扑：3D-torus ---
    dims: Tuple[int, int, int] = (4, 4, 4)        # kx × ky × kz，默认 64 个 TPU-like chip

    # --- 训练任务 ---
    target_steps: int = 2000                      # 目标训练步数
    msg_bytes: int = 512 * 1024 * 1024            # 每次 AllReduce 的梯度张量 512 MiB
    compute_seconds: float = 0.40                 # 每步前向 + 反向计算时间（不含 AllReduce）

    # --- 网络（ICI 链路）---
    link_bandwidth_bps: float = 50.0e9            # 50 GByte/s 每条 torus 链路
    link_latency_s: float = 1.0e-6                # 每跳 1 us

    # --- 故障 ---
    per_chip_fail_rate_per_hour: float = 2.0e-3   # 每芯片每小时硬故障率
    seed: int = 0
    max_step_budget: int = 5_000_000              # 防御性熔断：避免极端配置下死循环

    # --- checkpoint ---
    ckpt_interval: int = 100
    ckpt_seconds: float = 20.0

    # --- 恢复策略（见 recovery.py，对应 NSDI'24 的两条真实恢复路径 + 一个裸部署基线）---
    strategy: str = "reconfigure"                 # naive | reconfigure | reroute
    # Path 1（reconfigure）—— 迁移到空闲健康 cube，从 checkpoint 恢复
    ocs_reroute_seconds: float = 30.0             # OCS 光路重配，把作业接到空闲健康 cube
    migrate_seconds: float = 60.0                 # 重调度 + preflight + 重编译 + 载入 checkpoint
    abandoned_chips: int = 8                      # 被放弃的坏 cube 在后台修复期间闲置的芯片数
    background_repair_seconds: float = 1800.0     # 坏 cube 后台修复耗时（fleet 闲置的时长）
    # Path 2（reroute）—— 保留分配，重载容错 ICI 路由表（wild-first routing），继续跑
    reroute_seconds: float = 10.0                 # 重载预计算容错路由表的停机（远短于迁移）
    reroute_step_penalty: float = 0.05            # 每次 reroute 给后续每步叠加的步时惩罚（NSDI: 0.5%–8.6%）
    # naive —— 无自动化韧性的裸部署
    manual_repair_seconds: float = 600.0          # 人工诊断 + 物理修复的基础停机
    naive_downtime_multiplier: float = 3.0        # naive 停机倍数（等待人工，最长）

    def __post_init__(self) -> None:
        assert all(d >= 2 for d in self.dims), "torus 每个维度至少为 2（才能成环）"
        assert self.target_steps > 0, "target_steps 必须为正"
        assert self.link_bandwidth_bps > 0, "链路带宽必须为正"
        assert self.link_latency_s >= 0, "链路延迟不能为负"
        assert self.per_chip_fail_rate_per_hour >= 0, "故障率不能为负"
        assert self.ckpt_interval > 0, "checkpoint 间隔必须为正"
        assert self.strategy in {"naive", "reconfigure", "reroute"}, \
            f"未知策略: {self.strategy}"


@dataclass
class SimResult:
    """一次模拟的结果。"""

    completed: bool
    target: int
    steps_done: int                       # 最终提交（commit）的步数
    wasted_steps: int                     # 因故障回滚 / 重试而作废的步数
    useful_seconds: float                 # 真正推进训练的计算时间（= steps_done × 基础步时，不含 reroute tax）
    wall_seconds: float                   # 总挂钟时间（含 reroute tax / 恢复 / checkpoint 开销）
    ckpt_seconds: float
    recovery_seconds: float               # 作业停机（恢复）总时间
    fleet_idle_chip_seconds: float        # 集群闲置芯片·秒（reconfigure 放弃坏 cube 的代价）
    failures: int
    reconfigures: int                     # Path 1 触发次数
    reroutes: int                         # Path 2 触发次数
    final_step_penalty: float             # reroute 累积的步时惩罚（其它策略为 0）
    total_chips: int
