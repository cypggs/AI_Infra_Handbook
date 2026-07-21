"""TrainWorker：执行 PPO/GRPO 更新。

真实世界：Megatron-LM / FSDP / DeepSpeed 分布式训练。
Mini Demo：用"启发式梯度"更新 bigram logits——根据 advantage 把
每个 (prev, next) 的 logit 朝目标方向推一步。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .algorithms import kl_divergence, ppo_clip_loss
from .buffer import Experience
from .model import TinyPolicy


@dataclass
class TrainWorker:
    """执行 PPO 更新。

    - policy: 要训练的策略模型
    - ref_policy: 参考模型（KL 约束）
    - learning_rate: 学习率
    - kl_beta: KL 惩罚系数
    - clip_eps: PPO clip 范围
    """

    policy: TinyPolicy
    ref_policy: TinyPolicy
    learning_rate: float = 0.05
    kl_beta: float = 0.05
    clip_eps: float = 0.2

    # 最近一次 update 的 metric
    last_metrics: dict = field(default_factory=dict)

    def update(self, batch: list[Experience]) -> dict:
        """对一个 batch 执行一次 PPO 更新。

        返回 metrics：
        - mean_loss
        - mean_kl
        - ratio_clip_frac
        - mean_advantage
        """
        if not batch:
            return {}

        total_loss = 0.0
        total_kl = 0.0
        clipped_count = 0
        total_advantage = 0.0
        token_count = 0

        for exp in batch:
            # 重新计算 logprobs（新策略）
            logprobs_new = self.policy.sequence_logprob(exp.prompt, exp.response)
            logprobs_ref = self.ref_policy.sequence_logprob(exp.prompt, exp.response)

            # 逐 token 计算 loss / KL / clip
            for i, (ln, lo, lr) in enumerate(zip(logprobs_new, exp.logprobs_old, logprobs_ref)):
                loss, was_clipped = ppo_clip_loss(
                    ln, lo, exp.advantage, self.clip_eps
                )
                kl = kl_divergence(ln, lr)
                total_loss += loss
                total_kl += kl
                clipped_count += int(was_clipped)
                token_count += 1

                # 启发式梯度更新：
                # advantage > 0 且没被 clip → 提高该 token 的 logit
                # advantage < 0 且没被 clip → 降低该 token 的 logit
                # KL 大 → 把 logit 拉向 ref
                if not was_clipped:
                    prev = exp.prompt[-1] if i == 0 else exp.response[i - 1]
                    nxt = exp.response[i]
                    grad = exp.advantage * self.learning_rate
                    # KL 惩罚项：把 policy 往 ref 拉
                    kl_grad = -self.kl_beta * (ln - lr) * self.learning_rate
                    self.policy.update_logit(prev, nxt, grad + kl_grad)

            total_advantage += exp.advantage

        # 权重版本 +1（模拟 optimizer.step 后的权重更新）
        self.policy.version += 1

        metrics = {
            "mean_loss": total_loss / max(token_count, 1),
            "mean_kl": total_kl / max(token_count, 1),
            "ratio_clip_frac": clipped_count / max(token_count, 1),
            "mean_advantage": total_advantage / len(batch),
            "weight_version": self.policy.version,
        }
        self.last_metrics = metrics
        return metrics

    def get_weights(self) -> TinyPolicy:
        """返回当前权重的深拷贝（用于同步到 RolloutWorker）。"""
        return self.policy.clone()

    def reset_ref_policy(self) -> None:
        """把 ref_policy 同步为当前 policy（每 N step 调用一次）。"""
        self.ref_policy = self.policy.clone()
