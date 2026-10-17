"""端到端演示：5 个场景复现 xAI Colossus 案例的核心权衡。

运行::

    python -m xai_case_mini.demo
"""

from . import build, cooling, network, power


def scenario_build_schedule() -> dict[str, object]:
    """场景 1：建设排程——教科书串行 vs Colossus 式压缩。"""
    report = build.compression_report()
    print("== 场景 1：建设排程（关键路径分析）==")
    print(f"教科书串行流程 makespan : {report['conventional_days']} 天")
    print(f"Colossus 式流程集群就绪 : {report['cluster_ready_days']} 天"
          f"（全部任务收尾 {report['aggressive_days']} 天，电网扩容在后台）")
    print(f"压缩倍数                : {report['compression_ratio']:.2f}x")
    print(f"首次训练开始            : 第 {report['first_training_day']} 天")
    print(f"电网扩容完工（后台）    : 第 {report['grid_upgrade_done_day']} 天")
    print("压缩流程关键路径        : " + " -> ".join(report["aggressive_critical_path"]))
    print("参考：NVIDIA 官方口径为 122 天建成 / 首柜上架后 19 天开始训练\n")
    return report


def scenario_power_gap() -> dict[str, object]:
    """场景 2：供电缺口——Colossus 1 从 10 万卡扩到 20 万卡时的电力账。"""
    demand_100k = power.training_demand_mw(100_000, "H100-SXM")
    demand_200k = power.training_demand_mw(200_000, "H100-SXM")
    print("== 场景 2：供电缺口时间线（Colossus 1 扩展）==")
    print(f"10 万卡 H100 设施负载   : {demand_100k:.1f} MW（电网 150 MW 够用）")
    print(f"20 万卡 H100 设施负载   : {demand_200k:.1f} MW（超出电网批准 150 MW）")

    # 计划 A：等电网扩容（第 180 天批下第二个 150 MW）
    plan_a = power.PowerPlan(grid_mw=150.0, turbines=[], horizon_days=365)
    plan_a.turbines = [(180, 15)]  # 180 天后电网扩容到位（用 15 台轮机建模）
    # 计划 B：先上 35 台燃气轮机（Memphis 案例的做法）
    plan_b = power.PowerPlan(grid_mw=150.0, turbines=[(45, 35)], horizon_days=365)

    def summarize(plan, label):
        days = plan.days_of_shortfall(demand_200k)
        worst = plan.max_shortfall_mw(demand_200k)
        ok = plan.first_day_meeting(demand_200k)
        print(f"{label}: 缺口 {days} 天，最大缺口 {worst:.1f} MW，"
              f"首次满足需求第 {ok} 天")
        return {"days_of_shortfall": days, "max_shortfall_mw": worst,
                "first_ok_day": ok}

    a = summarize(plan_a, "计划 A（纯等电网扩容）")
    b = summarize(plan_b, "计划 B（第 45 天起 35 台燃气轮机）")
    print()
    return {"demand_100k_mw": demand_100k, "demand_200k_mw": demand_200k,
            "plan_a": a, "plan_b": b}


def scenario_single_vs_multi_campus() -> dict[str, object]:
    """场景 3：单一大集群 vs 双园区的 AllReduce 对比（梯度消息维度）。"""
    rows = network.campus_comparison(n_gpus=100_000)
    print("== 场景 3：单集群 vs 双园区 AllReduce（10 万卡，随梯度消息大小）==")
    print(f"{'梯度(GB)':>8} {'单集群(s)':>10} {'双园区(s)':>10} "
          f"{'惩罚(s)':>9} {'吞吐损失':>8}")
    for r in rows:
        print(f"{r['message_gb']:>8.0f} {r['single_s']:>10.2f} {r['dual_s']:>10.2f} "
              f"{r['penalty_s']:>9.2f} {r['throughput_loss']:>7.1%}")
    print("结论：跨园区惩罚随模型（消息）大小线性增长，而 DCI 带宽不会")
    print("      随模型增长——单训练域是 xAI 用 122 天换来的核心赌注\n")
    return {"rows": rows}


def scenario_roce_vs_ib() -> dict[str, object]:
    """场景 4：fabric 效率假设对比（Spectrum-X 官方口径）。"""
    message_bytes = 1024 * 1024 ** 3  # 1 TB
    comp = network.fabric_comparison(message_bytes)
    compute_s = 20.0  # 假设每步纯计算 20 秒
    print("== 场景 4：RoCE(Spectrum-X) vs 传统以太网 vs InfiniBand ==")
    base = comp["infiniband"]
    for name, t in comp.items():
        mfu = network.step_time(t, compute_s).mfu
        print(f"{name:>16}: AllReduce {t:6.2f} s（相对 IB {t / base:4.2f}x），"
              f"假设计算 20 s/步时 MFU={mfu:.3f}")
    print("参考：NVIDIA 官方口径 Spectrum-X 95% 吞吐 / 传统以太网约 60%\n")
    return {"compute_s": compute_s, "fabric_times_s": comp}


def scenario_cooling_density() -> dict[str, object]:
    """场景 5：风冷 vs 液冷的机柜密度与能耗。"""
    print("== 场景 5：风冷 vs 液冷（10 万卡集群）==")
    results = {}
    for gpu in ("H100-SXM", "GB200"):
        rows = cooling.cooling_comparison(100_000, gpu)
        results[gpu] = rows
        print(f"-- {gpu} 10 万张 --")
        for r in rows:
            print(f"  {r.cooling:>4}: 每柜 {r.gpus_per_rack:>2} 卡，"
                  f"需 {r.racks:>5} 柜，"
                  f"年耗电 {r.annual_energy_mwh:,.0f} MWh，"
                  f"CO2 ~{r.annual_co2_tons:,.0f} 吨/年")
    print("结论：液冷把机柜数砍到约 1/2.2，PUE 再省 ~14% 电量\n")
    return results


def main() -> None:
    print("=" * 64)
    print("xAI Colossus 超集群建设核心权衡模拟（CPU / 确定性）")
    print("=" * 64 + "\n")
    scenario_build_schedule()
    scenario_power_gap()
    scenario_single_vs_multi_campus()
    scenario_roce_vs_ib()
    scenario_cooling_density()
    print("演示完成。测试入口: pytest tests/ -v")


if __name__ == "__main__":
    main()
