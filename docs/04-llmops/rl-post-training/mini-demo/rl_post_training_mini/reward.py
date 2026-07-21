"""RewardService：可验证奖励 + Reward Model 混合。

真实世界：数学用 sympy 比对，代码用 subprocess 跑测试，主观用 RM。
Mini Demo：用规则模拟"可验证"，用 TinyRewardModel 模拟"主观"。
"""
from __future__ import annotations

from dataclasses import dataclass

from .buffer import Experience
from .model import TinyRewardModel


@dataclass
class RewardService:
    """评分服务。

    - verifiable_weight: 混合奖励中可验证奖励的权重 α
    - use_hackable_rm: 是否使用可被 hack 的 Reward Model（用于演示 reward hacking）
    """

    reward_model: TinyRewardModel
    verifiable_weight: float = 0.7
    use_hackable_rm: bool = False

    def score(self, exp: Experience) -> float:
        """对一条经验打分，写入 exp.reward 并返回。"""
        verifiable = self._verifiable_reward(exp)
        if self.use_hackable_rm:
            rm = self.reward_model.hackable_score(exp.prompt, exp.response)
        else:
            rm = self.reward_model.score(exp.prompt, exp.response)

        final = self.verifiable_weight * verifiable + (1 - self.verifiable_weight) * rm
        exp.reward = final
        exp.metadata["verifiable_reward"] = verifiable
        exp.metadata["rm_score"] = rm
        return final

    def _verifiable_reward(self, exp: Experience) -> float:
        """模拟可验证奖励：根据 task_type 用不同规则。"""
        text = "".join(exp.response)
        if exp.task_type == "math":
            # 数学题：response 包含 "42" 视为正确
            return 1.0 if "42" in text else 0.0
        elif exp.task_type == "code":
            # 代码题：包含 "def" 且长度合理
            return 1.0 if ("def" in text and 5 <= len(text) <= 30) else 0.0
        else:
            # 通用对话：长度合理且包含元音字母
            has_vowel = any(c in "aeiou" for c in text)
            reasonable = 5 <= len(text) <= 30
            return 1.0 if (has_vowel and reasonable) else 0.0

    def score_batch(self, exps: list[Experience]) -> list[float]:
        """批量打分。"""
        return [self.score(e) for e in exps]
