"""Speculative Edits 命中率与加速比模型。

官方公开口径（cursor.com/blog/instant-apply）：
- Apply = 整文件重写（不用 diff，因为 diff 需要输出行号且易漂移）
- Speculative Edits = 投机解码的变体：以"现有文件本身"作为确定性草稿，
  未改动区域可以成批验证而不是逐 token 生成
- 效果口径：约 1000 tok/s（~3500 字符/s），约 13x 于 Llama-3-70B 朴素推理，
  约 9x 于上一代 GPT-4 speculative 部署（Fireworks 推理引擎）

本模块把一次编辑抽象为 token 序列：未改动 token 可被草稿批量验证
（每 VERIFY_BATCH 个 token 一步），改动 token 必须逐步生成。
命中率 = 被验证 token 占比；加速比 = 朴素逐步生成时间 / 投机时间。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

VERIFY_BATCH = 32  # 教学值：一次验证步最多确认的未改动 token 数


def simulate_edit(
    n_tokens: int,
    edit_rate: float,
    seed: int = 7,
) -> dict[str, float]:
    """模拟一次整文件重写的投机编辑过程。

    返回确定性统计：changed/verified 数、命中率、相对朴素生成的加速比
    （假设生成与验证的单 token 代价相同；真实系统验证更便宜，加速比更高）。
    """
    rng = np.random.default_rng(seed)
    changed = rng.random(n_tokens) < edit_rate
    verified_steps = 0
    gen_steps = 0
    i = 0
    while i < n_tokens:
        if changed[i]:
            gen_steps += 1
            i += 1
        else:
            run = 0
            while i < n_tokens and not changed[i]:
                run += 1
                i += 1
            verified_steps += int(np.ceil(run / VERIFY_BATCH))
    n_changed = int(changed.sum())
    n_verified = n_tokens - n_changed
    vanilla_steps = float(n_tokens)
    spec_steps = float(gen_steps + verified_steps)
    return {
        "n_tokens": float(n_tokens),
        "n_changed": float(n_changed),
        "n_verified": float(n_verified),
        "hit_rate": n_verified / n_tokens,
        "speedup": vanilla_steps / spec_steps,
        "gen_steps": float(gen_steps),
        "verify_steps": float(verified_steps),
    }


@dataclass
class ApplyEngine:
    """把官方口径数字代入的教学模型：vanilla_tps -> 投机后 tok/s。"""

    vanilla_tps: float = 108.0  # 教学值：5% 改动率下约 9.3x 加速后约 1000 tok/s，
    # 对齐官方 ~1000 tok/s 口径（官方 13x 对应其自有模型与更便宜的验证实现）

    def fast_apply_tps(self, speedup: float) -> float:
        return self.vanilla_tps * speedup

    def edit_wall_time_ms(self, n_tokens: int, speedup: float) -> float:
        return n_tokens / self.fast_apply_tps(speedup) * 1000.0


def scan_edit_rate(n_tokens: int = 8192, rates=None) -> list[tuple[float, float, float]]:
    """扫不同改动率：返回 (edit_rate, hit_rate, speedup) 列表。

    教学结论：改动率越低（真实编辑大多只动局部），投机命中率越高、加速比越大。
    """
    rates = rates if rates is not None else [0.02, 0.05, 0.10, 0.20, 0.40]
    out = []
    for r in rates:
        s = simulate_edit(n_tokens, r, seed=7)
        out.append((r, round(s["hit_rate"], 4), round(s["speedup"], 2)))
    return out
