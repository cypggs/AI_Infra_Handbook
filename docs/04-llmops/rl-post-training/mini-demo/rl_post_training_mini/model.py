"""微型"语言模型"：bigram 概率模型。

真实世界：70B Transformer + PagedAttention。
Mini Demo：一张 bigram 概率表，但保留了 sample / logprob / update 三个接口，
让我们能演示 RL 的全部机制而无需 GPU。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class TinyPolicy:
    """Bigram 策略模型：给定前一个 token，预测下一个 token 的概率分布。

    - vocab: 词表（小写字母 + 空格 + eos）
    - logits: dict[(prev_token, next_token)] -> logit
    - temperature: 采样温度
    """

    vocab: list[str]
    logits: dict[tuple[str, str], float] = field(default_factory=dict)
    temperature: float = 1.0
    version: int = 0  # 权重版本号，每次 update 自增

    @classmethod
    def create(cls, seed: int = 0) -> "TinyPolicy":
        """构造一个初始化的 bigram 模型。"""
        rng = random.Random(seed)
        vocab = list("abcdefghijklmnopqrstuvwxyz .") + ["<eos>"]
        logits: dict[tuple[str, str], float] = {}
        for prev in vocab:
            for nxt in vocab:
                logits[(prev, nxt)] = rng.gauss(0.0, 0.1)
        return cls(vocab=vocab, logits=logits)

    def _distribution(self, prev_token: str) -> list[float]:
        """给定 prev token，返回下一个 token 的概率分布。"""
        scores = [
            self.logits.get((prev_token, tok), 0.0) / max(self.temperature, 1e-6)
            for tok in self.vocab
        ]
        max_score = max(scores)
        exp_scores = [math.exp(s - max_score) for s in scores]
        total = sum(exp_scores)
        return [s / total for s in exp_scores]

    def sample(self, prompt: str, max_length: int, rng: random.Random) -> list[str]:
        """自回归采样：从 prompt 最后一个 token 开始，逐个生成直到 <eos> 或达到 max_length。"""
        if not prompt:
            prev = " "
        else:
            prev = prompt[-1]
        out: list[str] = []
        for _ in range(max_length):
            probs = self._distribution(prev)
            # 加权随机采样
            r = rng.random()
            cumsum = 0.0
            chosen = self.vocab[-1]
            for tok, p in zip(self.vocab, probs):
                cumsum += p
                if r <= cumsum:
                    chosen = tok
                    break
            if chosen == "<eos>":
                break
            out.append(chosen)
            prev = chosen
        return out

    def logprob(self, prev_token: str, next_token: str) -> float:
        """计算 log P(next_token | prev_token)。"""
        probs = self._distribution(prev_token)
        try:
            idx = self.vocab.index(next_token)
        except ValueError:
            return -20.0  # 未登录 token
        p = probs[idx]
        return math.log(max(p, 1e-12))

    def sequence_logprob(self, prompt: str, response: list[str]) -> list[float]:
        """返回 response 中每个 token 的 logprob 列表。"""
        logprobs: list[float] = []
        prev = prompt[-1] if prompt else " "
        for tok in response:
            logprobs.append(self.logprob(prev, tok))
            prev = tok
        return logprobs

    def update_logit(self, prev_token: str, next_token: str, delta: float) -> None:
        """更新一个 logit（模拟梯度下降）。"""
        key = (prev_token, next_token)
        self.logits[key] = self.logits.get(key, 0.0) + delta

    def clone(self) -> "TinyPolicy":
        """深拷贝当前权重。"""
        return TinyPolicy(
            vocab=list(self.vocab),
            logits=dict(self.logits),
            temperature=self.temperature,
            version=self.version,
        )


@dataclass
class TinyRewardModel:
    """模拟 Reward Model：对 (prompt, response) 打 [0, 1] 分。

    真实 RM 是一个 scalar head Transformer；这里用一个简单启发式：
    - 包含 "good" 子串 → 高分
    - 包含 "bad" 子串 → 低分
    - 长度合理（5-20） → 加分
    - 否则 → 中位数
    """

    bias: float = 0.0  # 可被 "hack"：如果模型发现 bias 规律就会刷分

    def score(self, prompt: str, response: list[str]) -> float:
        text = "".join(response)
        score = 0.5 + self.bias
        if "good" in text:
            score += 0.4
        if "bad" in text:
            score -= 0.4
        length = len(response)
        if 5 <= length <= 20:
            score += 0.1
        elif length > 50:
            score -= 0.2  # 防止长度爆炸
        return max(0.0, min(1.0, score))

    def hackable_score(self, prompt: str, response: list[str]) -> float:
        """模拟可被 hack 的 RM：模型发现重复某个 token 会得高分。"""
        text = "".join(response)
        # 如果 response 全是同一字符，RM 错误地给高分
        if len(set(text)) == 1 and len(text) > 10:
            return 0.95
        return self.score(prompt, response)
