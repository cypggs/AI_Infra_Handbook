"""半异步/异步训练的正确性测试：版本打标、深度上界、TIS 修正。"""
from __future__ import annotations

import math

from rl_post_training_mini.algorithms import truncated_is_weight
from rl_post_training_mini.buffer import Experience, split_by_lag


def _exp(version: int, gid: int = 0) -> Experience:
    return Experience(
        prompt="p",
        response=["a"],
        logprobs_old=[-1.0],
        group_id=gid,
        weight_version=version,
    )


def test_truncated_is_weight_no_clip_in_range():
    """ratio = 1 时权重为 1，不截断。"""
    w, clipped = truncated_is_weight(-1.0, -1.0, clip_eps=0.2)
    assert not clipped
    assert w == 1.0


def test_truncated_is_weight_clipped_above():
    """ratio 超过 1+ε 时截断到 1+ε。"""
    w, clipped = truncated_is_weight(math.log(1.5), 0.0, clip_eps=0.2)
    assert clipped
    assert abs(w - 1.2) < 1e-9


def test_truncated_is_weight_clipped_below():
    """ratio 低于 1-ε 时截断到 1-ε。"""
    w, clipped = truncated_is_weight(math.log(0.5), 0.0, clip_eps=0.2)
    assert clipped
    assert abs(w - 0.8) < 1e-9


def test_split_by_lag_accepts_within_bound():
    """lag <= max_lag 的样本被接受。"""
    items = [_exp(4), _exp(3), _exp(2), _exp(5)]  # 5 是"未来"版本，也拒绝
    accepted, rejected = split_by_lag(items, current_version=4, max_lag=1)
    assert accepted == [items[0], items[1]]
    assert rejected == [items[2], items[3]]


def test_split_by_lag_all_fresh():
    """全部同版本时全部接受。"""
    items = [_exp(4), _exp(4)]
    accepted, rejected = split_by_lag(items, current_version=4, max_lag=1)
    assert len(accepted) == 2
    assert rejected == []
