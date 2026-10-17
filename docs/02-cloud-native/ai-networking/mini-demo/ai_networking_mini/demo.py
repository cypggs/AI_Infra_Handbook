"""6 个端到端场景：把拓扑、流量、拥塞、集合通信串成一个完整故事。

运行：python -m ai_networking_mini.demo
"""

from __future__ import annotations

from . import collective, congestion, topology, traffic

GIB = 1024 ** 3


def scenario_1_fat_tree() -> dict:
    """场景 1：fat-tree 拓扑生成与二分带宽。"""
    topo, info = topology.build_fat_tree(k=8, bw=400e9)
    hist = topo.hop_histogram()
    result = {
        "k": 8,
        "n_hosts": info.n_hosts,
        "n_switches": info.n_switches,
        "n_links": info.n_links,
        "bisection_bw_tb": info.bisection_bw / 1e12,
        "oversubscription": info.oversubscription,
        "hop_histogram": hist,
    }
    print("=== 场景 1：fat-tree 拓扑与二分带宽 ===")
    print(f"k=8 fat-tree: {info.n_hosts} 台主机, {info.n_switches} 台交换机, "
          f"{info.n_links} 条链路")
    print(f"二分带宽 {info.bisection_bw / 1e12:.1f} Tb/s, 收敛比 {info.oversubscription}")
    print(f"跳数分布(跳数:主机对数): {hist}")
    return result


def scenario_2_rail() -> dict:
    """场景 2：rail-optimized vs leaf-spine 的跳数与交换机数量。"""
    hosts, nics = 64, 8
    rail_topo, rail_info = topology.build_rail_optimized(hosts, nics)
    cmp_ = topology.compare_switch_count(hosts, nics)
    result = {
        "n_hosts": hosts,
        "nics_per_host": nics,
        "rail_switches": rail_info.n_switches,
        "leaf_spine_switches": cmp_["leaf_spine_switches"],
        "saved": cmp_["saved"],
        "saved_ratio": cmp_["saved_ratio"],
        "same_rail_hops": rail_topo.hop_count("host-0", "host-63"),
        "cross_rail_hops": topology.cross_rail_hops(),
    }
    print("\n=== 场景 2：rail-optimized vs leaf-spine ===")
    print(f"{hosts} 台主机 × {nics} 网卡：")
    print(f"  leaf-spine 需交换机 {cmp_['leaf_spine_switches']} 台 "
          f"({cmp_['leaf_spine_leaf']} leaf + {cmp_['leaf_spine_spine']} spine)")
    print(f"  rail-only   需交换机 {rail_info.n_switches} 台 (每 rail 一台)")
    print(f"  节省 {cmp_['saved']} 台（{cmp_['saved_ratio']:.0%}），"
          f"代价：跨 rail 流量要绕行 scale-up 域（fabric {topology.cross_rail_hops()} 跳）")
    return result


def scenario_3_traffic_matrix() -> dict:
    """场景 3：并行策略流量矩阵对比。"""
    config = {
        "params_bytes": 7e9,             # 7B 参数 MoE 模型
        "n_ranks": 256,
        "tp_message_bytes": 128 * 1024 * 1024,   # 每次 TP all-reduce 128MiB
        "n_tp": 8,
        "ep_token_bytes": 64 * 1024 * 1024,      # 每 microbatch EP 入向 token 激活
        "topk": 8,
        "n_ep": 64,
        "local_layers": 10,
        "n_microbatches": 16,
        "activation_bytes": 32 * 1024 * 1024,    # 每个 microbatch 的 stage 间激活
    }
    rows = traffic.step_traffic_summary(config)
    dominant = traffic.dominant_traffic(rows)
    print("\n=== 场景 3：一次训练 step 的并行策略流量 ===")
    for name, r in rows.items():
        print(f"  {name}: {r['bytes_per_rank'] / GIB:.2f} GiB/rank/step, "
              f"模式 {r['pattern']}")
    print(f"  -> 每 step 流量主导者: {dominant}")

    # 热点因子：均匀 all-to-all vs 倾斜 all-to-all（MoE 热门 expert）
    n = 64
    uniform = traffic.uniform_alltoall_matrix(n, 8 * 1024 * 1024)
    skewed = traffic.skewed_alltoall_matrix(n, 8 * 1024 * 1024, skew=3.0)
    su = traffic.matrix_stats(uniform)
    ss = traffic.matrix_stats(skewed)
    print(f"  all-to-all 均匀: hotspot={su['hotspot_factor']:.2f}, "
          f"incast={su['incast_factor']:.2f}")
    print(f"  all-to-all 倾斜(MoE 热 expert): hotspot={ss['hotspot_factor']:.2f}, "
          f"incast={ss['incast_factor']:.2f}")
    result = {"rows": {k: r["bytes_per_rank"] for k, r in rows.items()},
              "dominant": dominant,
              "uniform_hotspot": su["hotspot_factor"],
              "skewed_hotspot": ss["hotspot_factor"]}
    return result


def scenario_4_dcqcn() -> dict:
    """场景 4：incast 队列冲击 + ECN/DCQCN 速率收敛。"""
    n = 32
    msg = 4 * 1024 * 1024          # 每 sender 4MiB
    egress_bw = 400e9
    t = congestion.incast_completion_time(n, msg, egress_bw, 2e-6)
    q = congestion.incast_queue_peak(n, msg)
    print("\n=== 场景 4：incast 与 ECN/DCQCN ===")
    print(f"{n} 个 sender 同时向一个 400G 端口各发 {msg // 1024 // 1024}MiB：")
    print(f"  完成时间 {t * 1e6:.1f} µs，队列瞬时峰值 {q / 1024 / 1024:.0f} MiB")
    print(f"  ECN 标记概率: Kmin=64KiB Kmax=1MiB 时 "
          f"q={int(q)} -> {congestion.ecn_mark_probability(q, 64 * 1024, 1024 * 1024):.2f}")

    # DCQCN：前 16 步持续拥塞（每步都收 CNP），后 16 步空闲
    line = 400e9
    sched = [True] * 16 + [False] * 16
    sim = congestion.dcqcn_simulate(32, sched, line, init_rate_bps=line)
    rates = sim["rates"]
    print(f"  DCQCN：线速 {line / 1e9:.0f}G 起步，前 16 步每步收 CNP，后 16 步空闲")
    print(f"    16 步后速率 {rates[16] / 1e9:.1f} Gbps（降至 "
          f"{rates[16] / line:.0%}）")
    print(f"    32 步后速率 {rates[32] / 1e9:.1f} Gbps")
    result = {"incast_us": t * 1e6, "queue_peak_mib": q / 1024 / 1024,
              "rate_after_congestion_gbps": rates[16] / 1e9,
              "rate_after_recovery_gbps": rates[32] / 1e9,
              "rates": rates}
    return result


def scenario_5_pfc_deadlock() -> dict:
    """场景 5：PFC 死锁检测。"""
    deadlock_deps = congestion.classic_pfc_deadlock()
    ok_deps = congestion.deadlock_free_updown()
    d1, cyc = congestion.detect_deadlock(deadlock_deps)
    d2, _ = congestion.detect_deadlock(ok_deps)
    print("\n=== 场景 5：PFC 缓冲区依赖死锁 ===")
    print(f"  经典 up-down 路由四流成环: 死锁={d1}, 环路 {' -> '.join(cyc)}")
    print(f"  DAG 式单向依赖(对照组): 死锁={d2}")
    result = {"deadlock": d1, "cycle": cyc, "deadlock_free": d2}
    return result


def scenario_6_collectives() -> dict:
    """场景 6：ring vs tree all-reduce，跨 fabric 对比 + Amdahl。"""
    n = 128
    small = 4 * 1024 * 1024        # 4MiB 小消息（时延敏感）
    large = 4 * 1024 * 1024 * 1024  # 4GiB 大消息（带宽敏感）
    print("\n=== 场景 6：ring vs tree all-reduce（128 rank）===")
    for label, m in [("4MiB 小消息", small), ("4GiB 大消息", large)]:
        r = collective.compare_allreduce(n, m, "InfiniBand NDR 400G")
        print(f"  {label}: ring {r['ring']['time_s'] * 1e3:.2f} ms "
              f"({r['ring']['steps']} 步) vs tree {r['tree']['time_s'] * 1e3:.2f} ms "
              f"({r['tree']['steps']} 步) -> {r['winner']} 胜（{r['reason']}）")

    rows = collective.compare_fabrics(n, large, "ring")
    print("  同一 all-reduce 在不同 fabric（4GiB 大消息）：")
    for row in rows:
        print(f"    {row['fabric']:<24} {row['time_s'] * 1e3:10.2f} ms")

    # 网络提速对整个 step 的加速（Amdahl）
    amd = collective.step_speedup_from_faster_network(
        compute_time_s=1.0, comm_time_old_s=0.4, comm_time_new_s=0.1)
    print(f"  通信占 step {amd['comm_fraction_before']:.0%} 时，通信提速 4x "
          f"只换来 step 加速 {amd['speedup']:.2f}x（Amdahl）")
    result = {"small_winner": collective.compare_allreduce(n, small)["winner"],
              "large_winner": collective.compare_allreduce(n, large)["winner"],
              "fabric_order": [r["fabric"] for r in rows],
              "amdahl_speedup": amd["speedup"]}
    return result


ALL_SCENARIOS = [scenario_1_fat_tree, scenario_2_rail, scenario_3_traffic_matrix,
                 scenario_4_dcqcn, scenario_5_pfc_deadlock, scenario_6_collectives]


def main() -> None:
    results = [fn() for fn in ALL_SCENARIOS]
    assert len(results) == 6
    print("\n✅ 全部 6 个 AI 集群网络场景通过")


if __name__ == "__main__":
    main()
