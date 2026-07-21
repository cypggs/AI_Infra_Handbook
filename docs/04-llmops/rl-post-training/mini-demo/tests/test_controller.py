"""Controller 编排与权重版本同步测试。"""
from __future__ import annotations

from rl_post_training_mini.clock import FakeClock
from rl_post_training_mini.controller import Controller
from rl_post_training_mini.model import TinyPolicy, TinyRewardModel
from rl_post_training_mini.reward import RewardService
from rl_post_training_mini.rollout import RolloutWorker
from rl_post_training_mini.trainer import TrainWorker


def make_controller(seed: int = 0):
    clock = FakeClock()
    policy = TinyPolicy.create(seed=seed)
    ref = policy.clone()
    rm = TinyRewardModel()
    rollout = RolloutWorker(policy=policy, clock=clock, seed=seed)
    reward = RewardService(reward_model=rm)
    train = TrainWorker(policy=policy, ref_policy=ref)
    return Controller(
        rollout_worker=rollout,
        reward_service=reward,
        train_worker=train,
    )


def test_step_increments_version():
    """每个 step 后 weight_version 自增。"""
    c = make_controller()
    v0 = c.train_worker.policy.version
    c.step([("task", "chat")])
    v1 = c.train_worker.policy.version
    assert v1 == v0 + 1
    c.step([("task", "chat")])
    assert c.train_worker.policy.version == v0 + 2


def test_rollout_worker_synced_after_step():
    """step 结束后 RolloutWorker 权重版本应与 TrainWorker 一致。"""
    c = make_controller()
    c.step([("task", "chat")])
    assert c.rollout_worker.policy.version == c.train_worker.policy.version


def test_metrics_recorded():
    """每个 step 的 metric 都被记录。"""
    c = make_controller()
    for _ in range(3):
        c.step([("task", "chat")])
    assert len(c.history) == 3
    for i, m in enumerate(c.history):
        assert m["step"] == i
        assert "mean_reward" in m
        assert "mean_kl" in m
        assert "ratio_clip_frac" in m


def test_grpo_advantage_zero_mean_per_step():
    """每个 step 的 advantage 之和应接近 0（GRPO 性质）。"""
    c = make_controller()
    # 跑一步，检查内部 buffer
    c.step([("a", "chat"), ("b", "chat")])
    # 无法直接访问内部 buffer，通过 mean_advantage 间接验证
    m = c.history[-1]
    # mean_advantage 是 batch 均值，GRPO 组内 zero-mean 意味着全局也接近 zero-mean
    assert abs(m["mean_advantage"]) < 0.5
