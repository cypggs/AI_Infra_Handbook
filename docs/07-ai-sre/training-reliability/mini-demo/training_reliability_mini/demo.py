"""One-shot entry point: runs the five mini-demo scenarios.

Every scenario is deterministic (fixed seeds), so the printed numbers are
stable and are quoted verbatim in
``docs/07-ai-sre/training-reliability/07-mini-demo.md``.
"""
from __future__ import annotations

import numpy as np

from . import availability, checkpoint, recovery, sdc, straggler


def scenario_availability() -> str:
    """Scenario 1: MTBF/MTTR vs cluster scale."""
    lines = ["# 场景 1：可用率 vs 集群规模（MTBF/MTTR 模型）",
             "",
             "校准：节点 MTBF = 8089.6 h（Kokolis HPCA'25：1024 卡作业 MTTF 7.9 h 反推）",
             "",
             "| 节点数 | 作业 MTBF (h) | 冷修复 MTTR=60min 可用率 | 热备交换 MTTR=5min 可用率 |",
             "|---|---|---|---|"]
    for row in availability.scale_table(availability.NODE_MTBF_RESEARCH_CLUSTER_H):
        lines.append(
            f"| {row['nodes']} | {row['job_mtbf_h']:.3f} "
            f"| {row['avail_cold'] * 100:.2f}% | {row['avail_hot'] * 100:.2f}% |")
    lines += [
        "",
        f"Llama 3 口径校准：16,384 卡实测每 {availability.LLAMA3_INTERRUPTION_INTERVAL_H:.2f} h 一次中断"
        f"（隐含单节点 MTBF {availability.NODE_MTBF_LLAMA3_H / 24 / 365:.2f} 年）",
        f"1024 卡模型 MTBF = {availability.job_mtbf_hours(1024, availability.NODE_MTBF_RESEARCH_CLUSTER_H):.2f} h"
        "（实测锚点 7.9 h，Kokolis HPCA'25）",
    ]
    return "\n".join(lines)


def scenario_checkpoint() -> str:
    """Scenario 2: optimal checkpoint interval."""
    step_s, ckpt_s, mtbf_h, restart_s = 30.0, 240.0, 7.9, recovery.TIMELINE_COLD_RESTART_MIN * 60.0
    daly_s = checkpoint.daly_optimal_interval_s(ckpt_s, mtbf_h)
    opt = checkpoint.optimal_interval_grid(step_s, ckpt_s, mtbf_h, restart_s)
    no_ckpt = checkpoint.long_run_efficiency(5000, step_s, ckpt_s, mtbf_h, restart_s)
    inc = checkpoint.optimal_interval_grid(step_s, ckpt_s * 0.3, mtbf_h, restart_s)
    lines = [
        "# 场景 2：checkpoint 间隔优化",
        "",
        f"参数：step={step_s:.0f}s，全量 checkpoint 阻塞 {ckpt_s:.0f}s，"
        f"MTBF={mtbf_h} h（1024 卡作业），冷重启 {restart_s:.0f}s（TrainMover 8,192 卡拆解）",
        "",
        f"- 不 checkpoint：长程效率 {no_ckpt * 100:.2f}%（故障丢失全部进度）",
        f"- Daly 近似最优间隔：{daly_s / step_s:.0f} 步",
        f"- 网格精确最优：{opt['interval_steps']} 步，效率 {opt['efficiency'] * 100:.2f}%",
        f"- 差量 checkpoint（开销 x0.3）后最优：{inc['interval_steps']} 步，"
        f"效率 {inc['efficiency'] * 100:.2f}%",
        "",
        "间隔-效率曲线（节选）：",
        "",
        "| 间隔 (步) | 全量效率 | 差量效率 |",
        "|---|---|---|",
    ]
    curve = checkpoint.efficiency_curve(step_s, ckpt_s, mtbf_h, restart_s, every=100)
    curve_inc = {r["interval_steps"]: r["efficiency"]
                 for r in checkpoint.efficiency_curve(step_s, ckpt_s * 0.3, mtbf_h, restart_s, every=100)}
    for r in curve[2::3]:
        t = r["interval_steps"]
        lines.append(f"| {t} | {r['efficiency'] * 100:.2f}% | {curve_inc[t] * 100:.2f}% |")
    return "\n".join(lines)


def scenario_recovery() -> str:
    """Scenario 3: failure injection + elastic recovery."""
    duration_h, n_nodes = 24.0 * 7, 1024
    node_mtbf = availability.NODE_MTBF_RESEARCH_CLUSTER_H
    step_s, interval_steps = 30.0, 120
    cold = recovery.simulate_run(duration_h, n_nodes, node_mtbf, step_s, interval_steps, "cold", seed=7)
    hot = recovery.simulate_run(duration_h, n_nodes, node_mtbf, step_s, interval_steps, "hot", seed=7)
    lines = [
        "# 场景 3：故障注入 + 弹性恢复（7 天，1024 卡）",
        "",
        "恢复时间线常数：TrainMover 8,192 卡冷重启 6.47 min"
        "（停机 0.52 + 重调度 1.50 + ckpt 加载 1.56 + NCCL 1.09 + warmup 1.80）；"
        "ByteRobust 热备 hot-update 55 s（实测 46-65 s），检测 GPU 10s / NIC 30s / OS 2s",
        "",
        f"种子 7 注入故障 {cold['interruptions']} 次，分类分布：{cold['per_category']}",
        "",
        "| 策略 | 丢失工时 (h) | ETTR |",
        "|---|---|---|",
        f"| 冷重启（全量 requeue） | {cold['lost_h']:.3f} | {cold['ettr'] * 100:.2f}% |",
        f"| 热备（warm standby） | {hot['lost_h']:.3f} | {hot['ettr'] * 100:.2f}% |",
        "",
        "软件/other 类故障热备也救不了（需全量重启），这是热备池要按故障分类"
        "配置的原因之一。",
    ]
    return "\n".join(lines)


def scenario_straggler() -> str:
    """Scenario 4: straggler detection and mitigation."""
    n, step_s, sigma_s = 1024, 30.0, 0.5
    times = straggler.simulate_jittered_ranks(n, step_s, sigma_s, seed=11,
                                              slow_ranks={7: 1.2})
    flagged = set(int(i) for i in straggler.detect_stragglers(times, threshold=0.15))
    report = straggler.detection_report({7}, flagged)
    fixed = straggler.mitigate(times, np.array(sorted(flagged)), replacement_time_s=step_s)
    lines = [
        "# 场景 4：straggler 检测与缓解（1024 卡，rank 7 慢 20%）",
        "",
        f"- 同步语义下 step = max(rank 时间)：{straggler.step_time_s(times):.2f} s（基准 {step_s:.0f} s，拖尾 +20%）",
        f"- 中位数法检出慢节点：{sorted(flagged)}（precision={report['precision']:.2f}, "
        f"recall={report['recall']:.2f}）",
        f"- 替换后 step：{straggler.step_time_s(fixed):.2f} s（回到无慢节点基线）",
        "",
        "对照（无慢节点，sigma=0.5s 抖动）：",
    ]
    clean = straggler.simulate_jittered_ranks(n, step_s, sigma_s, seed=11)
    clean_flagged = straggler.detect_stragglers(clean, threshold=0.15)
    lines.append(f"- step = {straggler.step_time_s(clean):.2f} s，误报 {clean_flagged.size} 个")
    return "\n".join(lines)


def scenario_sdc() -> str:
    """Scenario 5: SDC dual-run detection."""
    rng = np.random.RandomState(5)
    n_ranks, dim = 1024, 4096
    shards = np.vstack([sdc.deterministic_grad(int(s), dim) for s in rng.randint(0, 10**6, n_ranks)])
    # Inject SDC into 8 ranks: 1-8 random bit flips each.
    corrupted = shards.copy()
    injected: set[int] = set()
    r2 = np.random.RandomState(9)
    for _ in range(8):
        rank = int(r2.randint(0, n_ranks))
        injected.add(rank)
        corrupted[rank] = sdc.inject_bit_flips(shards[rank], int(r2.randint(1, 9)), seed=rank)
    located = {int(i) for i in sdc.locate_corrupted_shards(shards, corrupted)}
    dual_hits = sum(
        1 for s in (11, 22, 33, 44, 55, 66, 77, 88)
        if sdc.dual_run_compare(int(s), dim=dim, n_flips=4, inject_seed=int(s))["mismatch"]
    )
    # Loss-spike guard on a decaying loss curve with one spike at step 500.
    losses = 2.5 * np.exp(-np.arange(1000) / 400.0) + 0.1
    losses[500] *= 50.0
    spikes = sdc.spike_indices(losses, factor=5.0)
    clean_losses = 2.5 * np.exp(-np.arange(1000) / 400.0) + 0.1
    clean_spikes = sdc.spike_indices(clean_losses, factor=5.0)
    lines = [
        "# 场景 5：SDC 双跑对比检测（1024 rank x 4096 维梯度）",
        "",
        f"- 注入 bit flip 的 rank：{sorted(injected)}（每 rank 1-8 个 bit）",
        f"- 分片指纹定位到 {len(located)} 个 rank：{sorted(located)}"
        f"（精确匹配 = {located == injected}）",
        f"- 双跑逐位对比 8 个样本：检出 {dual_hits}/8",
        f"- 干净数据双跑：误报 0",
        f"- loss 尖刺检测（5x 滚动中位数）：步 {[int(i) for i in spikes]} 命中注入点 500；"
        f"干净曲线误报 {int(clean_spikes.size)} 次",
        "",
        "注意：指纹定位是串行逐个对比（n_ranks 次），生产系统会把它摊进"
        "通信栈（如 NCCL 内嵌 checksum / 校验和聚合）。",
    ]
    return "\n".join(lines)


SCENARIOS = [
    scenario_availability,
    scenario_checkpoint,
    scenario_recovery,
    scenario_straggler,
    scenario_sdc,
]


def main() -> None:
    for i, fn in enumerate(SCENARIOS, start=1):
        print(fn())
        print()


if __name__ == "__main__":
    main()
