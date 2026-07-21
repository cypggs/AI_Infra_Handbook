"""RolloutWorker：模拟 vLLM 生成 + Continuous Batching。

真实世界：vLLM V1 + PagedAttention + Prefix Caching。
Mini Demo：用 TinyPolicy.sample 模拟逐 token 生成，
并用 FakeClock 精确复现 wall time（Continuous Batching 让长短样本并行）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .buffer import Experience
from .clock import Clock
from .model import TinyPolicy


@dataclass
class RolloutWorker:
    """生成 Rollout 的 worker。

    - policy: 当前的策略模型（权重）
    - clock: 时钟（用于测量生成耗时）
    - seed: 随机种子
    - token_time_per_token: 模拟每生成一个 token 的耗时（秒）
    """

    policy: TinyPolicy
    clock: Clock
    seed: int = 0
    token_time: float = 0.01  # 每 token 生成耗时

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def generate(
        self,
        prompts: list[tuple[str, int, str]],  # (prompt_text, group_id, task_type)
        group_size: int,
        max_length: int,
        weight_version: int,
        continuous_batching: bool = True,
    ) -> list[Experience]:
        """为每个 prompt 生成 group_size 个 response。

        continuous_batching=True 时：模拟 vLLM 迭代级调度，总耗时 = max(各样本耗时)
        continuous_batching=False 时：模拟静态批处理，总耗时 = sum(各样本耗时)
        """
        # 权重版本守护：Rollout 用的版本必须与 Controller 下发的一致
        if weight_version != self.policy.version:
            raise ValueError(
                f"Weight version mismatch: rollout asked v{weight_version}, "
                f"but worker has v{self.policy.version}"
            )

        experiences: list[Experience] = []
        longest = 0
        total_tokens = 0

        for prompt_text, gid, task_type in prompts:
            for _ in range(group_size):
                response = self.policy.sample(prompt_text, max_length, self._rng)
                logprobs = self.policy.sequence_logprob(prompt_text, response)
                exp = Experience(
                    prompt=prompt_text,
                    response=response,
                    logprobs_old=logprobs,
                    group_id=gid,
                    weight_version=weight_version,
                    task_type=task_type,
                )
                experiences.append(exp)
                longest = max(longest, len(response))
                total_tokens += len(response)

        # 模拟耗时：CB 让长短样本并行，静态批处理串行
        if continuous_batching:
            elapsed = longest * self.token_time
        else:
            elapsed = total_tokens * self.token_time
        self.clock.sleep(elapsed)

        return experiences

    def update_weights(self, new_policy: TinyPolicy, expected_version: int) -> None:
        """热加载新权重。"""
        if new_policy.version != expected_version:
            raise ValueError(
                f"Weight version mismatch on load: got v{new_policy.version}, "
                f"expected v{expected_version}"
            )
        self.policy = new_policy
