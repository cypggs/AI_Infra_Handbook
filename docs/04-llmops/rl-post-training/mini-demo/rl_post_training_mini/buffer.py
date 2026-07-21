"""经验缓冲：Rollout 产出的样本在这里中转，供 Train 消费。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Experience:
    """单条 RL 经验。

    - prompt / response: 输入输出
    - logprobs_old: 生成时（旧策略）每个 token 的 logprob
    - reward: 评分服务给出的奖励
    - advantage: Train 阶段填充（GRPO 组内归一化）
    - group_id: 同一 prompt 的 G 个 sample 共享 group_id
    - weight_version: 生成时使用的权重版本（用于 On-Policy 守护）
    - task_type: 任务类型（math / code / chat），路由不同 reward
    """

    prompt: str
    response: list[str]
    logprobs_old: list[float]
    group_id: int
    weight_version: int
    task_type: str = "chat"
    reward: float = 0.0
    advantage: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ExperienceBuffer:
    """在线 buffer（On-Policy）：每个 step 消费完即清空。"""

    items: list[Experience] = field(default_factory=list)

    def add(self, exp: Experience) -> None:
        self.items.append(exp)

    def extend(self, exps: list[Experience]) -> None:
        self.items.extend(exps)

    def clear(self) -> None:
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)

    def rewards(self) -> list[float]:
        return [e.reward for e in self.items]

    def group_ids(self) -> list[int]:
        return [e.group_id for e in self.items]

    def mean_reward(self) -> float:
        if not self.items:
            return 0.0
        return sum(self.rewards()) / len(self.items)

    def mean_length(self) -> float:
        if not self.items:
            return 0.0
        return sum(len(e.response) for e in self.items) / len(self.items)
