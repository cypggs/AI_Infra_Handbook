"""google_mini：Google TPU 3D-torus 集合通信 + 训练可靠性模拟器。

复现 Google 超大规模 TPU 训练基础设施中最具辨识度的两组机制：
  1. 3D-torus 分维 ring AllReduce 的延迟优势（相对单一大环 / fat-tree）；
  2. NSDI'24《Resiliency at Scale》的两条真实恢复路径——reconfigure（迁移到空闲
     健康 cube）vs reroute（容错 ICI 路由，持续步时惩罚）——的双轴权衡。
纯 CPU、确定性、无需任何 LLM key。
"""
from .collective import (
    latency_term,
    ring_allreduce_time,
    single_ring_time,
    torus_allreduce_time,
)
from .failures import per_step_cluster_hazard, roll_failures, sample_failure
from .metrics import (
    ckpt_overhead_pct,
    effective_mfu,
    fleet_idle_chip_hours,
    recovery_overhead_pct,
    step_penalty_pct,
    wasted_step_pct,
)
from .model import JobConfig, SimResult
from .recovery import RecoveryOutcome, apply_strategy
from .simulator import TrainingSimulator
from .topology import Torus3D

__all__ = [
    "JobConfig",
    "SimResult",
    "Torus3D",
    "ring_allreduce_time",
    "torus_allreduce_time",
    "single_ring_time",
    "latency_term",
    "per_step_cluster_hazard",
    "roll_failures",
    "sample_failure",
    "apply_strategy",
    "RecoveryOutcome",
    "TrainingSimulator",
    "effective_mfu",
    "recovery_overhead_pct",
    "ckpt_overhead_pct",
    "wasted_step_pct",
    "fleet_idle_chip_hours",
    "step_penalty_pct",
]
