"""指标：有效训练时间（MFU）与各类开销。

与 Meta 案例的 effective_utilization 同口径：分子是真正推进模型前进的时间
（= 已提交步数 × 基础步时），分母是含一切 tax / 恢复 / checkpoint 开销的挂钟时间。
"""
from .model import SimResult


def effective_mfu(r: SimResult) -> float:
    """有效训练时间 = 有效计算时间 / 总挂钟时间。"""
    return r.useful_seconds / r.wall_seconds if r.wall_seconds > 0 else 0.0


def recovery_overhead_pct(r: SimResult) -> float:
    """恢复停机占总挂钟时间的百分比。"""
    return r.recovery_seconds / r.wall_seconds * 100.0 if r.wall_seconds > 0 else 0.0


def ckpt_overhead_pct(r: SimResult) -> float:
    """checkpoint 开销占总挂钟时间的百分比。"""
    return r.ckpt_seconds / r.wall_seconds * 100.0 if r.wall_seconds > 0 else 0.0


def wasted_step_pct(r: SimResult) -> float:
    """回滚 / 重试作废步数占（已提交 + 作废）的百分比。"""
    denom = r.steps_done + r.wasted_steps
    return r.wasted_steps / denom * 100.0 if denom > 0 else 0.0


def fleet_idle_chip_hours(r: SimResult) -> float:
    """集群闲置芯片·小时（reconfigure 放弃坏 cube 的代价）。"""
    return r.fleet_idle_chip_seconds / 3600.0


def step_penalty_pct(r: SimResult) -> float:
    """reroute 累积的步时惩罚百分比（其它策略为 0）。"""
    return r.final_step_penalty * 100.0
