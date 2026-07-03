"""故障模型：把"每芯片每小时故障率"换算成"每步集群风险"。

一个 size 个芯片的同步训练任务，任一芯片故障都会停顿整个集合通信——这正是
NSDI'24《Resiliency at Scale》的核心约束："To train a model, all TPU processes
must be simultaneously up to synchronously update their weights via ICI
collectives. A single failed, or interrupted process will interrupt the whole
training process." 因此每步集群风险 = 1 − (1 − p_chip)^size，size 落在指数上：
集群越大越脆弱。

为了让三种恢复策略面对 **完全相同的故障序列**（公平对比），我们用 seed 一次性
预抛出每个逻辑步是否故障，与策略无关、与控制流无关。
"""
import random
from typing import List


def per_step_cluster_hazard(
    per_chip_fail_rate_per_hour: float, n_chips: int, step_seconds: float
) -> float:
    """单芯片在一步内的故障概率 → 整个集群在一步内"至少一个芯片故障"的概率。"""
    p_chip = per_chip_fail_rate_per_hour * (step_seconds / 3600.0)
    return 1.0 - (1.0 - p_chip) ** n_chips


def roll_failures(rng: random.Random, n_steps: int, hazard: float) -> List[bool]:
    """预抛 n_steps 步的故障序列（可变：触发后置 False 以"消费"一次性故障）。"""
    return [rng.random() < hazard for _ in range(n_steps)]


def sample_failure(rng: random.Random, hazard: float) -> bool:
    """以 hazard 的概率采样一次故障（保留供单步测试使用）。"""
    return rng.random() < hazard
