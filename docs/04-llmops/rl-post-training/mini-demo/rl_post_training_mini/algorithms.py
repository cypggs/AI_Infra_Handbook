"""核心算法：GRPO advantage / PPO clip / KL penalty。

这些函数与 verl.trainer.ppo.core_algos 中的实现一一对应，
只是用纯 Python list 替代 torch tensor。
"""
from __future__ import annotations

import math


def compute_grpo_advantage(
    rewards: list[float],
    group_ids: list[int],
    eps: float = 1e-8,
) -> list[float]:
    """GRPO 的 advantage：组内归一化。

    对同一 prompt 生成的 G 个 response，计算 (r_i - mean_group) / (std_group + eps)。
    这样 advantage 自然 zero-mean，无需 Critic 网络。
    """
    if len(rewards) != len(group_ids):
        raise ValueError("rewards 和 group_ids 长度必须一致")

    groups: dict[int, list[int]] = {}
    for idx, gid in enumerate(group_ids):
        groups.setdefault(gid, []).append(idx)

    advantages = [0.0] * len(rewards)
    for gid, indices in groups.items():
        group_rewards = [rewards[i] for i in indices]
        mean = sum(group_rewards) / len(group_rewards)
        var = sum((r - mean) ** 2 for r in group_rewards) / len(group_rewards)
        std = math.sqrt(var)
        for i in indices:
            advantages[i] = (rewards[i] - mean) / (std + eps)
    return advantages


def ppo_clip_loss(
    logprob_new: float,
    logprob_old: float,
    advantage: float,
    clip_eps: float = 0.2,
) -> tuple[float, bool]:
    """PPO clipped surrogate loss（单个样本）。

    返回 (loss, was_clipped)。
    loss = -min(ratio * A, clip(ratio, 1-eps, 1+eps) * A)
    """
    ratio = math.exp(logprob_new - logprob_old)
    surr1 = ratio * advantage
    clipped_ratio = max(min(ratio, 1 + clip_eps), 1 - clip_eps)
    surr2 = clipped_ratio * advantage
    loss = -min(surr1, surr2)
    was_clipped = abs(ratio - clipped_ratio) > 1e-9
    return loss, was_clipped


def kl_divergence(
    logprob_policy: float,
    logprob_ref: float,
) -> float:
    """单 token 的 KL 散度近似：logp_policy - logp_ref。

    严格定义是 E[log(p/q)]，单 token 情况简化为差值。
    实际系统中是对整个 response 求均值。
    """
    return logprob_policy - logprob_ref


def sequence_kl(
    logprobs_policy: list[float],
    logprobs_ref: list[float],
) -> float:
    """序列级 KL：token KL 的均值。"""
    if len(logprobs_policy) != len(logprobs_ref):
        raise ValueError("logprobs 长度必须一致")
    if not logprobs_policy:
        return 0.0
    total = sum(
        kl_divergence(p, r) for p, r in zip(logprobs_policy, logprobs_ref)
    )
    return total / len(logprobs_policy)
