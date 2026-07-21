"""算法正确性测试：GRPO / PPO clip / KL。"""
from __future__ import annotations

import math

import pytest

from rl_post_training_mini.algorithms import (
    compute_grpo_advantage,
    kl_divergence,
    ppo_clip_loss,
    sequence_kl,
)


def test_grpo_advantage_zero_mean():
    """同组的 advantage 之和应接近 0（zero-mean）。"""
    rewards = [1.0, 0.5, 0.0, 0.8]
    group_ids = [0, 0, 0, 0]
    advs = compute_grpo_advantage(rewards, group_ids)
    assert abs(sum(advs)) < 1e-6


def test_grpo_advantage_group_normalized():
    """不同 group 独立归一化。"""
    rewards = [1.0, 0.0, 0.5, 0.5]
    group_ids = [0, 0, 1, 1]
    advs = compute_grpo_advantage(rewards, group_ids)
    # group 0: mean=0.5, std=0.5, adv=[1, -1]
    # group 1: mean=0.5, std=0, adv=[0, 0]
    assert advs[0] > 0
    assert advs[1] < 0
    assert abs(advs[2]) < 1e-6
    assert abs(advs[3]) < 1e-6


def test_grpo_advantage_single_sample_group():
    """组内只有一个样本时 advantage 为 0。"""
    rewards = [0.7]
    group_ids = [0]
    advs = compute_grpo_advantage(rewards, group_ids)
    assert advs == [0.0]


def test_grpo_advantage_length_mismatch():
    """rewards 和 group_ids 长度不一致时抛错。"""
    with pytest.raises(ValueError):
        compute_grpo_advantage([1.0], [0, 1])


def test_ppo_clip_no_clip_in_range():
    """ratio 在 [1-eps, 1+eps] 内时不 clip。"""
    # logprob 相同 → ratio = 1
    loss, clipped = ppo_clip_loss(-1.0, -1.0, advantage=1.0, clip_eps=0.2)
    assert not clipped
    assert loss == -1.0  # -min(1*1, 1*1)


def test_ppo_clip_clipped_above():
    """ratio > 1+eps 时被 clip。"""
    # logp_new - logp_old = ln(1.5) → ratio = 1.5 > 1.2
    logp_old = 0.0
    logp_new = math.log(1.5)
    loss, clipped = ppo_clip_loss(logp_new, logp_old, advantage=1.0, clip_eps=0.2)
    assert clipped
    # loss = -min(1.5*1, 1.2*1) = -1.2
    assert abs(loss - (-1.2)) < 1e-6


def test_ppo_clip_clipped_below():
    """ratio < 1-eps 时被 clip。"""
    logp_old = 0.0
    logp_new = math.log(0.5)  # ratio = 0.5 < 0.8
    loss, clipped = ppo_clip_loss(logp_new, logp_old, advantage=1.0, clip_eps=0.2)
    assert clipped
    # loss = -min(0.5*1, 0.8*1) = -0.5
    assert abs(loss - (-0.5)) < 1e-6


def test_ppo_clip_negative_advantage():
    """负 advantage 时 clip 逻辑反向。"""
    # ratio = 1.5, advantage = -1 → surr1 = -1.5, surr2 = -1.2
    # loss = -min(-1.5, -1.2) = 1.5
    logp_old = 0.0
    logp_new = math.log(1.5)
    loss, clipped = ppo_clip_loss(logp_new, logp_old, advantage=-1.0, clip_eps=0.2)
    # min(-1.5, -1.2) = -1.5, -(-1.5) = 1.5
    assert abs(loss - 1.5) < 1e-6


def test_kl_divergence():
    """单 token KL = logp_policy - logp_ref。"""
    assert kl_divergence(-1.0, -2.0) == 1.0
    assert kl_divergence(-2.0, -1.0) == -1.0


def test_sequence_kl():
    """序列 KL = 平均 token KL。"""
    policy = [-1.0, -2.0, -3.0]
    ref = [-1.5, -2.5, -3.5]
    kl = sequence_kl(policy, ref)
    assert abs(kl - 0.5) < 1e-6


def test_sequence_kl_empty():
    """空序列 KL 为 0。"""
    assert sequence_kl([], []) == 0.0


def test_sequence_kl_length_mismatch():
    with pytest.raises(ValueError):
        sequence_kl([1.0], [1.0, 2.0])
