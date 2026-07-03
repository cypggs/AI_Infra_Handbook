from google_mini.demo import (
    _baseline_config,
    _naive_config,
    _reconfigure_config,
    _reroute_config,
)
from google_mini.metrics import effective_mfu
from google_mini.simulator import TrainingSimulator


def _sim():
    return TrainingSimulator()


def test_baseline_completes_no_failures():
    r = _sim().run(_baseline_config(seed=7))
    assert r.completed is True
    assert r.failures == 0
    assert r.steps_done == r.target
    assert r.useful_seconds > 0.0
    assert r.final_step_penalty == 0.0


def test_same_seed_same_failure_sequence_across_strategies():
    """三种恢复策略面对完全相同的预抛故障序列 → failures / useful 完全一致。"""
    seed = 7
    naive = _sim().run(_naive_config(seed))
    rec = _sim().run(_reconfigure_config(seed))
    rer = _sim().run(_reroute_config(seed))
    assert naive.failures == rec.failures == rer.failures
    assert naive.failures >= 1, "演示故障率应保证至少一次故障"
    # 都跑满 target → 已提交步数相同 → useful（= steps_done × 基础步时）相同
    assert naive.useful_seconds == rec.useful_seconds == rer.useful_seconds
    assert naive.steps_done == rec.steps_done == rer.steps_done


def test_wasted_steps_reroute_leq_reconfigure():
    """reroute 不回滚（仅重试故障步），作废步数远少于会回滚的 reconfigure/naive。"""
    seed = 7
    rer = _sim().run(_reroute_config(seed))
    rec = _sim().run(_reconfigure_config(seed))
    naive = _sim().run(_naive_config(seed))
    assert rer.wasted_steps <= rec.wasted_steps
    assert rer.wasted_steps <= naive.wasted_steps


def test_wall_and_mfu_ordering():
    """reroute 停机最短、MFU 最高；naive 停机最长、MFU 最低。"""
    seed = 7
    naive = _sim().run(_naive_config(seed))
    rec = _sim().run(_reconfigure_config(seed))
    rer = _sim().run(_reroute_config(seed))
    assert naive.wall_seconds > rec.wall_seconds > rer.wall_seconds
    assert effective_mfu(rer) > effective_mfu(rec) > effective_mfu(naive)


def test_fleet_idle_only_for_reconfigure():
    seed = 7
    assert _sim().run(_reconfigure_config(seed)).fleet_idle_chip_seconds > 0.0
    assert _sim().run(_reroute_config(seed)).fleet_idle_chip_seconds == 0.0
    assert _sim().run(_naive_config(seed)).fleet_idle_chip_seconds == 0.0


def test_step_penalty_only_for_reroute():
    seed = 7
    assert _sim().run(_reroute_config(seed)).final_step_penalty > 0.0
    assert _sim().run(_reconfigure_config(seed)).final_step_penalty == 0.0
    assert _sim().run(_naive_config(seed)).final_step_penalty == 0.0


def test_reroute_penalty_increases_with_failures():
    """reroute 的累积步时惩罚 ≈ reroute_step_penalty × failures。"""
    r = _sim().run(_reroute_config(seed=7))
    assert abs(r.final_step_penalty - r.reroutes * 0.05) < 1e-9


def test_max_step_budget_aborts():
    cfg = _naive_config(seed=7)
    cfg.target_steps = 50
    cfg.max_step_budget = 3
    r = _sim().run(cfg)
    assert r.completed is False


def test_all_configs_complete_under_normal_budget():
    seed = 7
    for fn in (_naive_config, _reconfigure_config, _reroute_config):
        assert _sim().run(fn(seed)).completed is True
