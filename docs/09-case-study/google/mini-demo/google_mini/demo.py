"""入口：对比 基线 / naive / reconfigure / reroute 四种配置，
并打印 (1) 3D-torus 分维 AllReduce 相对单一大环的延迟优势；
(2) reconfigure vs reroute 在「稀疏故障 vs 频繁故障」下的 MFU 交叉——
    即 NSDI'24 双轴权衡（迁移停机 vs 持续步时惩罚）的定量体现。"""
from .collective import (
    latency_term,
    single_ring_time,
    torus_allreduce_time,
)
from .metrics import (
    effective_mfu,
    fleet_idle_chip_hours,
    recovery_overhead_pct,
    step_penalty_pct,
    wasted_step_pct,
)
from .model import JobConfig
from .simulator import TrainingSimulator

# 默认演示参数（同一 seed → 三种恢复策略面对完全相同的故障序列，便于公平对比）
_DEMO_DIMS = (4, 4, 4)
_DEMO_TARGET = 2000
_DEMO_MSG = 512 * 1024 * 1024
_DEMO_BW = 50.0e9
_DEMO_LAT = 1.0e-6
_DEMO_COMPUTE = 0.40
# 故障率被放大，以便在 2000 步的短模拟内观察到多次故障（真实 fleet 故障率远低于此）
_DEMO_FAIL_RATE = 0.35
# 交叉洞察用的两档故障率：稀疏（少量故障）vs 频繁（多次故障）
_SPARSE_FAIL_RATE = 0.04
_FREQUENT_FAIL_RATE = 0.60
# 步时惩罚扫描范围（NSDI'24 实测单次 reroute 步时惩罚 0.5%–8.6%）
_PENALTY_SWEEP = [0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.16, 0.20, 0.30]


def _base(seed: int, **overrides) -> JobConfig:
    cfg = JobConfig(
        dims=_DEMO_DIMS,
        target_steps=_DEMO_TARGET,
        msg_bytes=_DEMO_MSG,
        compute_seconds=_DEMO_COMPUTE,
        link_bandwidth_bps=_DEMO_BW,
        link_latency_s=_DEMO_LAT,
        per_chip_fail_rate_per_hour=_DEMO_FAIL_RATE,
        seed=seed,
        ckpt_interval=100,
        ckpt_seconds=20.0,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _baseline_config(seed: int) -> JobConfig:
    return _base(seed, per_chip_fail_rate_per_hour=0.0)


def _naive_config(seed: int) -> JobConfig:
    return _base(seed, strategy="naive")


def _reconfigure_config(seed: int) -> JobConfig:
    return _base(seed, strategy="reconfigure")


def _reroute_config(seed: int) -> JobConfig:
    return _base(seed, strategy="reroute")


def run_demo(seed: int = 7) -> dict:
    """跑四种配置，返回 {name: SimResult}。三种故障配置共享同一故障序列。"""
    sim = TrainingSimulator()
    return {
        "baseline": sim.run(_baseline_config(seed)),
        "naive": sim.run(_naive_config(seed)),
        "reconfigure": sim.run(_reconfigure_config(seed)),
        "reroute": sim.run(_reroute_config(seed)),
    }


def torus_vs_ring_insight() -> dict:
    """3D-torus 分维 AllReduce vs 单一大环（16×16×16 = 4096 芯片），两种消息规模。"""
    dims = (16, 16, 16)
    n = 16 ** 3
    bw, lat = 50.0e9, 1.0e-6
    big, small = 512 * 1024 * 1024, 1024
    return {
        "dims": dims,
        "n_chips": n,
        "latency_term_torus": latency_term(dims),          # 2·Σ(d-1) = 90
        "latency_term_ring": 2 * (n - 1),                  # 8190
        "big_msg_bytes": big,
        "big_torus_s": torus_allreduce_time(dims, big, bw, lat),
        "big_ring_s": single_ring_time(n, big, bw, lat),
        "small_msg_bytes": small,
        "small_torus_s": torus_allreduce_time(dims, small, bw, lat),
        "small_ring_s": single_ring_time(n, small, bw, lat),
    }


def _mfu_at(strategy: str, seed: int = 7, **overrides) -> float:
    cfg = _base(seed, strategy=strategy, **overrides)
    return effective_mfu(TrainingSimulator().run(cfg))


def reconfigure_vs_reroute_insight() -> dict:
    """reroute 的「持续步时惩罚」阈值扫描：找出 reconfigure 反超 reroute 的临界惩罚。

    reconfigure 的代价是结构性的（每次故障：迁移停机 + 回滚重跑 + fleet 闲置），与
    reroute 的步时惩罚无关，故其 MFU 在扫描中恒定。reroute 的 MFU 随每次故障叠加的
    步时惩罚增大而单调下降。二者相交的临界惩罚，就是「reroute 还划算」的上限——
    这正是 NSDI'24 实测单次 reroute 步时惩罚仅 0.5%–8.6%、并对 OCS 故障优先修复以
    缩短 reroute 时长的根因：只要 tax 小，reroute「不停机、不回滚」就压倒 reconfigure。
    """
    rec_mfu = _mfu_at("reconfigure")                     # 恒定基准
    sweep = []
    crossover = None
    for p in _PENALTY_SWEEP:
        rer_mfu = _mfu_at("reroute", reroute_step_penalty=p)
        sweep.append({"penalty": p, "reroute_mfu": rer_mfu})
        if crossover is None and rer_mfu < rec_mfu:
            crossover = p
    # 同一故障序列下两种策略的「省去的重启开销」对照（reroute 的标志性优势）
    sparse_rec = _mfu_at("reconfigure", per_chip_fail_rate_per_hour=_SPARSE_FAIL_RATE)
    sparse_rer = _mfu_at("reroute", per_chip_fail_rate_per_hour=_SPARSE_FAIL_RATE)
    return {
        "reconfigure_mfu": rec_mfu,
        "sweep": sweep,
        "crossover_penalty": crossover,                  # reroute MFU 跌破 reconfigure 的首个惩罚
        "sparse_reconfigure_mfu": sparse_rec,
        "sparse_reroute_mfu": sparse_rer,
    }


def _print_table(results: dict) -> None:
    print("Google TPU 3D-torus 训练可靠性模拟（reconfigure vs reroute，NSDI'24 双路径）")
    print("─" * 104)
    header = (
        f"{'配置':<24}{'有效训练MFU':>12}{'恢复停机%':>11}"
        f"{'步时惩罚%':>11}{'中断':>6}{'回滚步%':>9}{'集群闲置(chip·h)':>20}"
    )
    print(header)
    print("─" * 104)
    names = {
        "baseline": "基线(无故障)",
        "naive": "naive(裸部署)",
        "reconfigure": "reconfigure(P1迁移)",
        "reroute": "reroute(P2容错路由)",
    }
    for key in ("baseline", "naive", "reconfigure", "reroute"):
        r = results[key]
        print(
            f"{names[key]:<24}"
            f"{effective_mfu(r) * 100:>11.1f}%"
            f"{recovery_overhead_pct(r):>10.1f}%"
            f"{step_penalty_pct(r):>10.1f}%"
            f"{r.failures:>6}"
            f"{wasted_step_pct(r):>8.1f}%"
            f"{fleet_idle_chip_hours(r):>20.1f}"
        )
    print("─" * 104)
    print("结论：naive（裸部署）停机最长、MFU 最低；reconfigure 用一次性迁移停机 +")
    print("      fleet 闲置换高 job MFU；reroute 几乎不停机但每步承受持续 tax（可累积）。")


def _print_topology_insight() -> None:
    info = torus_vs_ring_insight()
    print()
    print(f"拓扑洞察：{info['dims'][0]}×{info['dims'][1]}×{info['dims'][2]} = "
          f"{info['n_chips']} 芯片上的 AllReduce")
    print("─" * 64)
    print(f"  延迟项：torus 2·Σ(d-1) = {info['latency_term_torus']:.0f}   "
          f"单环 2·(N-1) = {info['latency_term_ring']:.0f}   "
          f"（torus 约为单环的 "
          f"{info['latency_term_torus']/info['latency_term_ring']*100:.1f}%）")
    big_kb = info["big_msg_bytes"] // 1024
    print(f"  大消息 {big_kb} KiB（带宽主导）：torus ≈ {info['big_torus_s']*1000:.2f} ms，"
          f"单环 ≈ {info['big_ring_s']*1000:.2f} ms")
    print(f"  小消息 {info['small_msg_bytes']} B（延迟主导）：torus ≈ "
          f"{info['small_torus_s']*1e6:.1f} µs，单环 ≈ {info['small_ring_s']*1e6:.0f} µs")
    print("─" * 64)
    print("结论：torus 的结构性收益在延迟项——按边长线性增长，而非按芯片总数指数增长；")
    print("      延迟主导的集合通信（频繁小 AllReduce）获益最大，带宽主导时收益收敛。")


def _print_crossover_insight() -> None:
    info = reconfigure_vs_reroute_insight()
    print()
    print("恢复路径阈值洞察：reroute 步时惩罚要多大，reconfigure 才反超？")
    print("─" * 72)
    print(f"  reconfigure MFU（恒定基准）= {info['reconfigure_mfu']*100:.1f}%")
    print("  reroute MFU 随每次故障叠加的步时惩罚下降：")
    for row in info["sweep"]:
        mark = "  ← reconfigure 反超" if row["reroute_mfu"] < info["reconfigure_mfu"] else ""
        print(f"      惩罚 {row['penalty']*100:>4.0f}%：reroute MFU = {row['reroute_mfu']*100:>5.1f}%{mark}")
    print("─" * 72)
    if info["crossover_penalty"] is not None:
        print(f"  临界惩罚 ≈ {info['crossover_penalty']*100:.0f}%：低于此值 reroute「不停机、不回滚」")
        print(f"  压倒 reconfigure；高于此值累积 tax 反噬。")
    print("  结论：NSDI'24 实测单次 reroute 步时惩罚仅 0.5%–8.6%（远低于临界），故 reroute 是")
    print("        默认路径（95% opt-in）；Google 优先修复 OCS 正是为了把 tax 控制在临界以内。")


def main() -> None:
    results = run_demo()
    _print_table(results)
    _print_topology_insight()
    _print_crossover_insight()


if __name__ == "__main__":
    main()
