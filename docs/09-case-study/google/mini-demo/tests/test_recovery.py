from google_mini.model import JobConfig
from google_mini.recovery import apply_strategy


def _cfg():
    return JobConfig(dims=(4, 4, 4), per_chip_fail_rate_per_hour=0.0)


def test_naive_slowest_rolls_back_no_tax_no_idle():
    cfg = _cfg()
    out = apply_strategy("naive", cfg, 64)
    assert out.job_downtime_seconds == cfg.manual_repair_seconds * cfg.naive_downtime_multiplier
    assert out.fleet_idle_chip_seconds == 0.0
    assert out.rollback is True
    assert out.step_penalty_increment == 0.0


def test_reconfigure_migrates_rolls_back_fleet_idle_no_tax():
    cfg = _cfg()
    out = apply_strategy("reconfigure", cfg, 64)
    assert out.job_downtime_seconds == cfg.ocs_reroute_seconds + cfg.migrate_seconds
    assert out.fleet_idle_chip_seconds == cfg.abandoned_chips * cfg.background_repair_seconds
    assert out.rollback is True
    assert out.step_penalty_increment == 0.0


def test_reroute_keeps_allocation_no_rollback_no_idle_with_tax():
    cfg = _cfg()
    out = apply_strategy("reroute", cfg, 64)
    assert out.job_downtime_seconds == cfg.reroute_seconds
    assert out.fleet_idle_chip_seconds == 0.0
    assert out.rollback is False          # NSDI Path 2：保留分配，不回滚
    assert out.step_penalty_increment == cfg.reroute_step_penalty  # 持续步时惩罚


def test_downtime_ordering_naive_reconfigure_reroute():
    cfg = _cfg()
    n = apply_strategy("naive", cfg, 64).job_downtime_seconds
    r = apply_strategy("reconfigure", cfg, 64).job_downtime_seconds
    u = apply_strategy("reroute", cfg, 64).job_downtime_seconds
    # naive（人工维修）> reconfigure（迁移）> reroute（重载路由表）
    assert n > r > u


def test_only_reroute_carries_a_tax():
    cfg = _cfg()
    taxes = {s: apply_strategy(s, cfg, 64).step_penalty_increment
             for s in ("naive", "reconfigure", "reroute")}
    assert taxes["naive"] == taxes["reconfigure"] == 0.0
    assert taxes["reroute"] > 0.0


def test_only_reconfigure_produces_fleet_idle():
    cfg = _cfg()
    idle = {s: apply_strategy(s, cfg, 64).fleet_idle_chip_seconds
            for s in ("naive", "reconfigure", "reroute")}
    assert idle["naive"] == idle["reroute"] == 0.0
    assert idle["reconfigure"] > 0.0
