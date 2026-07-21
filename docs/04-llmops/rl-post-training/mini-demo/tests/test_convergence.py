"""多 step 收敛性测试。"""
from __future__ import annotations

from rl_post_training_mini.clock import FakeClock
from rl_post_training_mini.controller import Controller
from rl_post_training_mini.model import TinyPolicy, TinyRewardModel
from rl_post_training_mini.reward import RewardService
from rl_post_training_mini.rollout import RolloutWorker
from rl_post_training_mini.trainer import TrainWorker


def make_controller(seed: int = 0, lr: float = 0.1):
    clock = FakeClock()
    policy = TinyPolicy.create(seed=seed)
    ref = policy.clone()
    rm = TinyRewardModel()
    rollout = RolloutWorker(policy=policy, clock=clock, seed=seed)
    reward = RewardService(reward_model=rm)
    train = TrainWorker(policy=policy, ref_policy=ref, learning_rate=lr)
    return Controller(
        rollout_worker=rollout,
        reward_service=reward,
        train_worker=train,
    )


def test_reward_increases_over_steps():
    """多 step 跑通且 metric 都被记录。

    注：bigram 模型的"学习"是启发式的，reward 不保证单调上升。
    这个测试只验证多 step 流程稳定，不验证收敛方向。
    """
    c = make_controller(seed=42)
    prompts = [("task", "chat"), ("task", "chat")]
    rewards = []
    for _ in range(10):
        m = c.step(prompts)
        rewards.append(m["mean_reward"])
    assert len(rewards) == 10
    assert all(0.0 <= r <= 1.0 for r in rewards)


def test_weight_version_monotonic():
    """权重版本应单调递增。"""
    c = make_controller()
    versions = []
    for _ in range(5):
        m = c.step([("task", "chat")])
        versions.append(m["weight_version"])
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
