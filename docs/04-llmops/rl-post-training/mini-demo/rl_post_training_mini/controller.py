"""Controller：RL step 编排器，对应 veRL RayPPOTrainer。

职责：
- 采样 prompt batch
- 调用 RolloutWorker 生成
- 调用 RewardService 评分
- 计算 GRPO advantage
- 调用 TrainWorker 更新
- 同步权重到 RolloutWorker
- 维护权重版本号
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .algorithms import compute_grpo_advantage
from .buffer import Experience, ExperienceBuffer
from .reward import RewardService
from .rollout import RolloutWorker
from .trainer import TrainWorker


@dataclass
class Controller:
    """RL 训练编排器。"""

    rollout_worker: RolloutWorker
    reward_service: RewardService
    train_worker: TrainWorker
    group_size: int = 4
    max_length: int = 30

    # 当前 step 计数
    step_count: int = 0
    # metric 历史
    history: list[dict] = field(default_factory=list)

    def step(
        self,
        prompts: list[tuple[str, str]],  # (prompt_text, task_type)
    ) -> dict:
        """执行一个完整的 RL step。

        返回 step metrics。
        """
        # 1. 准备 prompt 批次（附带 group_id）
        prompt_batch = [
            (text, gid, task)
            for gid, (text, task) in enumerate(prompts)
        ]

        # 2. 当前权重版本
        current_version = self.train_worker.policy.version

        # 3. Rollout 生成
        rollouts = self.rollout_worker.generate(
            prompt_batch,
            group_size=self.group_size,
            max_length=self.max_length,
            weight_version=current_version,
        )

        # 4. 守护：所有 rollout 必须用同一版本
        for r in rollouts:
            if r.weight_version != current_version:
                raise RuntimeError(
                    f"Stale rollout: v{r.weight_version} != v{current_version}"
                )

        # 5. Reward 评分
        self.reward_service.score_batch(rollouts)

        # 6. 计算 GRPO advantage
        buffer = ExperienceBuffer()
        buffer.extend(rollouts)
        advantages = compute_grpo_advantage(buffer.rewards(), buffer.group_ids())
        for exp, adv in zip(rollouts, advantages):
            exp.advantage = adv

        # 7. Train 更新
        train_metrics = self.train_worker.update(rollouts)

        # 8. 权重同步到 RolloutWorker
        new_weights = self.train_worker.get_weights()
        self.rollout_worker.update_weights(new_weights, expected_version=new_weights.version)

        # 9. 聚合 metrics
        step_metrics = {
            "step": self.step_count,
            "mean_reward": buffer.mean_reward(),
            "mean_length": buffer.mean_length(),
            **train_metrics,
        }
        self.history.append(step_metrics)
        self.step_count += 1

        return step_metrics

    def latest_metrics(self) -> dict:
        return self.history[-1] if self.history else {}
