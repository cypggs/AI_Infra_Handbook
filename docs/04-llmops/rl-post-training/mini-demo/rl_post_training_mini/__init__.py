"""rl_post_training_mini - 微型 RL Post-Training 教学模拟器

把 RL Post-Training 的核心机制（GRPO advantage / PPO clip / KL penalty /
Rollout-Train 分离 / 权重版本同步）用纯 Python 标准库重建，便于在 CPU 上
单步调试每一个工程决策。

模块与真实组件对照：

- model.py:        TinyPolicy / TinyRewardModel ≈ Transformer / Reward Model
- algorithms.py:   GRPO / PPO clip / KL penalty ≈ verl.trainer.ppo.core_algos
- rollout.py:      RolloutWorker ≈ vLLM 实例
- reward.py:       RewardService ≈ 可验证奖励 + Reward Model 服务
- trainer.py:      TrainWorker ≈ Megatron-LM / FSDP PPO
- controller.py:   Controller ≈ veRL RayPPOTrainer
- buffer.py:       ExperienceBuffer ≈ 经验缓冲
- clock.py:        FakeClock ≈ 分布式 trace 时间戳
"""

from .algorithms import (
    compute_grpo_advantage,
    kl_divergence,
    ppo_clip_loss,
)
from .buffer import Experience, ExperienceBuffer
from .clock import Clock, FakeClock, RealClock
from .controller import Controller
from .model import TinyPolicy, TinyRewardModel
from .reward import RewardService
from .rollout import RolloutWorker
from .trainer import TrainWorker

__all__ = [
    "Clock",
    "Controller",
    "Experience",
    "ExperienceBuffer",
    "FakeClock",
    "RealClock",
    "RewardService",
    "RolloutWorker",
    "TinyPolicy",
    "TinyRewardModel",
    "TrainWorker",
    "compute_grpo_advantage",
    "kl_divergence",
    "ppo_clip_loss",
]
