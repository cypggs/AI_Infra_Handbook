"""Rollout 与 logprob 一致性测试。"""
from __future__ import annotations

from rl_post_training_mini.clock import FakeClock
from rl_post_training_mini.model import TinyPolicy
from rl_post_training_mini.rollout import RolloutWorker


def test_logprobs_match_policy():
    """Rollout 返回的 logprob 必须与 policy 当前输出一致。"""
    clock = FakeClock()
    policy = TinyPolicy.create(seed=0)
    worker = RolloutWorker(policy=policy, clock=clock, seed=0)

    prompts = [("hello", 0, "chat")]
    exps = worker.generate(
        prompts, group_size=1, max_length=10, weight_version=0
    )
    exp = exps[0]
    # 用同一个 policy 重算 logprobs
    expected = policy.sequence_logprob(exp.prompt, exp.response)
    assert exp.logprobs_old == expected


def test_continuous_batching_speedup():
    """Continuous Batching 应该显著快于静态批处理。"""
    policy = TinyPolicy.create(seed=1)

    clock_cb = FakeClock()
    worker_cb = RolloutWorker(policy=policy, clock=clock_cb, seed=1, token_time=0.01)
    prompts = [(f"task{i}", i, "chat") for i in range(4)]
    worker_cb.generate(
        prompts, group_size=4, max_length=30,
        weight_version=0, continuous_batching=True,
    )

    clock_no_cb = FakeClock()
    worker_no_cb = RolloutWorker(policy=policy, clock=clock_no_cb, seed=1, token_time=0.01)
    worker_no_cb.generate(
        prompts, group_size=4, max_length=30,
        weight_version=0, continuous_batching=False,
    )

    assert clock_cb.now() < clock_no_cb.now()


def test_weight_version_guard():
    """权重版本不一致时 Rollout 应抛错。"""
    clock = FakeClock()
    policy = TinyPolicy.create(seed=0)
    policy.version = 5
    worker = RolloutWorker(policy=policy, clock=clock, seed=0)

    prompts = [("hello", 0, "chat")]
    try:
        worker.generate(
            prompts, group_size=1, max_length=5,
            weight_version=3,  # 与 policy.version=5 不一致
        )
    except ValueError as e:
        assert "version mismatch" in str(e).lower()
    else:
        raise AssertionError("应该抛 ValueError")


def test_update_weights_version_guard():
    """update_weights 版本不匹配时抛错。"""
    clock = FakeClock()
    policy = TinyPolicy.create(seed=0)
    worker = RolloutWorker(policy=policy, clock=clock, seed=0)

    new_policy = TinyPolicy.create(seed=1)
    new_policy.version = 7

    try:
        worker.update_weights(new_policy, expected_version=8)
    except ValueError:
        pass
    else:
        raise AssertionError("应该抛 ValueError")
