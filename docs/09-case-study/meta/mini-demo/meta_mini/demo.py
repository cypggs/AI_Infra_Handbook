"""Demo entry point: naive vs optimized vs ideal, with a comparison table.

Run with::

    python -m meta_mini.demo
"""

from __future__ import annotations

from meta_mini.metrics import (
    checkpoint_overhead_pct,
    effective_utilization,
    recompute_overhead_pct,
    validation_overhead_pct,
)
from meta_mini.model import JobConfig, SimResult
from meta_mini.simulator import TrainingSimulator


def _ideal_config(seed: int) -> JobConfig:
    """No failures at all — the pure checkpoint-overhead baseline."""
    return JobConfig(
        hard_fail_rate=0.0,
        sdc_rate=0.0,
        ckpt_interval=200,
        ckpt_seconds=30.0,
        validation_interval=100,
        validation_seconds=15.0,
        seed=seed,
    )


def _naive_config(seed: int) -> JobConfig:
    """Large checkpoint interval + no SDC validation: high rollback waste,
    every SDC gets baked into a checkpoint or the final weights."""
    return JobConfig(
        hard_fail_rate=8.0e-5,
        sdc_rate=6.0e-5,
        ckpt_interval=500,
        ckpt_seconds=60.0,
        validation_interval=0,        # no detector
        validation_seconds=0.0,
        seed=seed,
    )


def _optimized_config(seed: int) -> JobConfig:
    """Small checkpoint interval + frequent validation: low rollback waste,
    SDCs are caught before being baked in (validation_interval < ckpt_interval)."""
    return JobConfig(
        hard_fail_rate=8.0e-5,
        sdc_rate=6.0e-5,
        ckpt_interval=200,
        ckpt_seconds=30.0,
        validation_interval=100,
        validation_seconds=15.0,
        seed=seed,
    )


def run_demo(seed: int = 7) -> dict:
    """Run all three configurations and return their results.

    Returns a dict with keys ``"ideal"``, ``"naive"``, ``"optimized"`` mapping
    to ``SimResult``. Deterministic for a given ``seed``.
    """
    sim = TrainingSimulator()
    return {
        "ideal": sim.run(_ideal_config(seed)),
        "naive": sim.run(_naive_config(seed)),
        "optimized": sim.run(_optimized_config(seed)),
    }


def _fmt_pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _print_table(results: dict) -> None:
    rows: list[tuple[str, SimResult]] = [
        ("理想(无故障)", results["ideal"]),
        ("朴素(大间隔/无验证)", results["naive"]),
        ("优化(小间隔/频繁验证)", results["optimized"]),
    ]

    print("Meta 训练集群可靠性模拟（同步训练的故障经济学）")
    sep = "-" * 104
    print(sep)
    header = (
        f"{'配置':<22} {'有效训练时间':>12} {'回滚浪费':>9} "
        f"{'ckpt开销':>9} {'验证开销':>9} {'中断':>5} {'SDC检出':>7} {'SDC焊死':>7}"
    )
    print(header)
    print(sep)
    for name, r in rows:
        print(
            f"{name:<22} {_fmt_pct(effective_utilization(r)):>12} "
            f"{_fmt_pct(recompute_overhead_pct(r)):>9} "
            f"{_fmt_pct(checkpoint_overhead_pct(r)):>9} "
            f"{_fmt_pct(validation_overhead_pct(r)):>9} "
            f"{r.interruptions:>5} {r.sdc_detected:>7} {r.sdc_baked:>7}"
        )
    print(sep)
    naive, opt = results["naive"], results["optimized"]
    print(
        f"结论：优化配置把 SDC 焊死从 {naive.sdc_baked} 降到 {opt.sdc_baked}"
        f"（验证先于 checkpoint），用 checkpoint+验证开销换取回滚浪费"
        f"（{naive.sdc_detected} → {opt.sdc_detected} 检出）。"
    )


def main() -> None:
    _print_table(run_demo())


if __name__ == "__main__":
    main()
