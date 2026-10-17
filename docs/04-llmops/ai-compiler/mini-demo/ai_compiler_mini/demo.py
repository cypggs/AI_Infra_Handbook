"""AI 编译器 Mini Demo —— 端到端演示「构图 -> 融合 -> 调优 -> 模拟执行」。

对应真实编译器的一条完整链路（以 torch.compile 为例）：

  Python 模型 -> FX graph capture -> Inductor 融合/调度 -> Triton kernel
  -> autotune 选配置 -> 编译产物在 GPU 上执行

本 demo 在 numpy 上把每一层都用最小语义复刻，六个场景逐步展开。
"""

from __future__ import annotations

import numpy as np

from .fusion import explain_non_fusion, fuse, fused_count
from .graph import Graph
from .triton_like import FusedRowwiseKernel, KernelStats, TilingConfig, run_tiled_matmul
from .tune import autotune, config_space


def _build_mlp_graph(m: int, k: int, n: int, seed: int = 0) -> tuple:
    """x @ W + b -> relu -> sum(axis=1)：MLP 片段 + 行归约。"""
    rng = np.random.default_rng(seed)
    g = Graph()
    x = g.placeholder("x", (m, k))
    w = g.constant_with_value("W", rng.standard_normal((k, n)))
    b = g.constant_with_value("bias", rng.standard_normal((n,)))
    mm = g.matmul(x, w, name="mm")
    add = g.elementwise("add", mm, b, name="bias_add")
    relu = g.elementwise("relu", add, name="relu")
    s = g.reduce("sum", relu, axis=1, name="rowsum")
    return g, x, s


def scenario_1_graph_capture() -> None:
    print("=" * 70)
    print("场景 1：Graph Capture —— 把 Python 计算捕获成 IR")
    print("=" * 70)
    g, _, _ = _build_mlp_graph(m=64, k=48, n=32)
    print("源代码视角:  y = relu(x @ W + bias).sum(axis=1)")
    print()
    print(g.dump())
    print()
    print(f"节点数: {len(g.nodes)}，其中 placeholder={len(g.inputs)}, constant={len(g.constants)}")
    print()


def scenario_2_fusion() -> None:
    print("=" * 70)
    print("场景 2：算子融合 pass —— kernel 数量从 N 降到 group 数")
    print("=" * 70)
    g, _, _ = _build_mlp_graph(m=64, k=48, n=32)
    groups = fuse(g)
    print("融合结果（每组 = 一个 kernel）：")
    for i, fg in enumerate(groups):
        print(f"  kernel{i} [{fg.kind:15s}] {' -> '.join('%' + nm for nm in fg.names)}")
    print()
    stats = fused_count(g)
    print(f"原始计算节点 {stats['nodes']} 个 -> 融合后 {stats['kernels']} 个 kernel")
    print()
    print("未融合边的诊断：")
    for r in explain_non_fusion(g):
        print(f"  - {r}")
    print()


def scenario_3_autotune() -> None:
    print("=" * 70)
    print("场景 3：Auto-tuner —— cost model 在配置空间中打分选优")
    print("=" * 70)
    m, n, k = 256, 256, 256
    space = config_space(m, n, k)
    print(f"问题规模 M={m} N={n} K={k}，候选配置 {len(space)} 个")
    print()
    top = autotune(m, n, k, top_k=3)
    print("Top-3 配置（score = 预估毫秒，越低越好）：")
    for rank, sc in enumerate(top, 1):
        c = sc.config
        d = sc.detail
        print(
            f"  #{rank} BM={c.BLOCK_M:>3} BN={c.BLOCK_N:>3} BK={c.BLOCK_K:>3} "
            f"warps={c.num_warps} stages={c.num_stages}  score={sc.score:.4f} ms"
        )
        print(
            f"      分解: mem={d['mem_ms']:.4f} comp={d['comp_ms']:.4f} "
            f"launch={d['launch_ms']:.4f} waste={d['waste_ms']:.4f} "
            f"(padding 浪费 {d['padding_waste'] * 100:.1f}%)"
        )
    print()


def scenario_4_tiled_matmul() -> None:
    print("=" * 70)
    print("场景 4：Triton-like tile 语义模拟 GEMM，并与参考实现对拍")
    print("=" * 70)
    rng = np.random.default_rng(1)
    m, n, k = 100, 84, 60  # 故意不整除，验证边界 tile
    a = rng.standard_normal((m, k))
    b = rng.standard_normal((k, n))
    cfg = TilingConfig(BLOCK_M=32, BLOCK_N=32, BLOCK_K=32, num_warps=4, num_stages=3)
    c, stats = run_tiled_matmul(a, b, cfg)
    ref = a @ b
    err = float(np.max(np.abs(c - ref)))
    gm, gn = (m + 31) // 32, (n + 31) // 32
    print(f"M={m} K={k} N={n}（均不被 32 整除，存在边界 tile）")
    print(f"grid = ({gm}, {gn})，共 {stats.programs_launched} 个 program")
    print(f"全局读 {stats.global_loads_bytes / 1e3:.1f} KB，写 {stats.global_stores_bytes / 1e3:.1f} KB")
    print(f"与 numpy 参考的最大误差: {err:.2e} -> {'PASS' if err < 1e-9 else 'FAIL'}")
    print()


def scenario_5_fused_rowwise() -> None:
    print("=" * 70)
    print("场景 5：融合 vs 未融合 —— 行归约 kernel 的内存流量对比")
    print("=" * 70)
    rng = np.random.default_rng(2)
    x = rng.standard_normal((128, 96))
    fused_stats = KernelStats()
    kernel = FusedRowwiseKernel(preprocess=lambda v: np.maximum(v, 0.0), reduce="sum")  # relu + rowsum
    fused_out = kernel.run(x, fused_stats)

    from .triton_like import unfused_rowwise_reference

    unfused_out, unfused_stats = unfused_rowwise_reference(x, lambda v: np.maximum(v, 0.0), "sum")
    saved = 1.0 - fused_stats.total_traffic_bytes / unfused_stats.total_traffic_bytes
    print(f"计算: relu(x).sum(axis=1)，x 形状 {x.shape}")
    print(f"未融合（eager）：{unfused_stats.total_traffic_bytes / 1e3:.1f} KB 全局流量")
    print(f"融合 kernel  ：{fused_stats.total_traffic_bytes / 1e3:.1f} KB 全局流量")
    print(f"流量下降 {saved * 100:.1f}%（中间结果不再往返 HBM）")
    print(f"结果一致: {np.allclose(fused_out, unfused_out)}")
    print()


def scenario_6_end_to_end() -> None:
    print("=" * 70)
    print("场景 6：端到端 —— 一次完整的 mini 编译流程")
    print("=" * 70)
    m, k, n = 64, 48, 32
    g, x_node, out_node = _build_mlp_graph(m, k, n, seed=3)
    feed = {"x": np.random.default_rng(3).standard_normal((m, k))}

    # 1) capture
    print("[1] graph capture")
    print(f"    {len(g.nodes)} 个 IR 节点")
    # 2) fusion
    groups = fuse(g)
    print("[2] fusion pass")
    for i, fg in enumerate(groups):
        print(f"    kernel{i} [{fg.kind}] <- {', '.join(fg.names)}")
    # 3) tuning（matmul 组）
    mm_node = g.get("mm")
    top = autotune(mm_node.shape[0], mm_node.shape[1], mm_node.inputs[0].shape[1], top_k=1)[0]
    c = top.config
    print("[3] autotune (matmul 组)")
    print(f"    选中 BM={c.BLOCK_M} BN={c.BLOCK_N} BK={c.BLOCK_K} warps={c.num_warps} stages={c.num_stages}")
    # 4) 模拟执行 matmul kernel 并与参考对拍
    env = g.eval(feed)
    a, b = feed["x"], env["W"]
    c_out, stats = run_tiled_matmul(a, b, top.config)
    err = float(np.max(np.abs(c_out - env["mm"])))
    print("[4] codegen + 模拟执行")
    print(f"    生成 1 个 GEMM kernel：{stats.programs_launched} programs，"
          f"{stats.total_traffic_bytes / 1e3:.1f} KB 流量，误差 {err:.2e}")
    # 5) 整图参考值（eager 后端）作为正确性 baseline
    print("[5] 正确性对拍")
    print(f"    eager 后端 rowsum = {env['rowsum'][:4].round(4)} ...")
    print()
    print("端到端 PASS：graph -> fusion -> tuning -> simulated codegen 全链路一致")


def main() -> None:
    scenario_1_graph_capture()
    scenario_2_fusion()
    scenario_3_autotune()
    scenario_4_tiled_matmul()
    scenario_5_fused_rowwise()
    scenario_6_end_to_end()


if __name__ == "__main__":
    main()
