"""6 个端到端演示场景：端侧与边缘推理的核心权衡（纯 numpy、确定性）。

场景：
1. bandwidth_decode —— 带宽受限 decode 吞吐模型：位宽、带宽、利用率如何决定 tok/s
2. kv_capacity      —— KV cache 容量规划：GQA + KV 量化决定上下文上限
3. hetero_fallback  —— NPU/GPU/CPU 异构算子放置与回退税
4. mmap_streaming   —— 闪存流式加载：缺页、预取窗口与工作集
5. lora_switch      —— LoRA 热切换 vs 权重合并的内存/时延权衡
6. edge_cloud_route —— 端云混合路由：隐私/SLO/成本/热节流的联合决策

每个场景返回一个 dict（键稳定），tests/test_demo.py 会对关键数字做断言。
"""

from __future__ import annotations

from . import hetero, lora, memory, routing, speculative, streaming
from .hetero import Device, Op

# ---------------------------------------------------------------------------
# 场景共享的端侧画像（虚构但量级贴近 2025-2026 旗舰手机）
# ---------------------------------------------------------------------------
PHONE = {
    "bandwidth_gbs": 68.0,       # LPDDR5X 级统一内存带宽
    "total_gib": 8.0,
    "reserve_gib": 0.8,          # OS + 运行时 + 图形栈保留
    "utilization": 0.85,
    "params": 8e9,               # Llama-3-8B 量级
    "layers": 32,
    "kv_heads": 8,               # GQA
    "head_dim": 128,
    "hidden": 4096,
    "ffn": 11008,
    "q4_bits": 4.8,              # Q4_K_M 类混合量化等效位宽
    "fp16_bits": 16.0,
    "page_bytes": 16 * 1024,     # 16 KiB 页
    "fault_us": 25.0,            # 一次缺页的经验开销
    "fabric_gbs": 60.0,          # 片内统一内存 fabric 带宽
}


# ---------------------------------------------------------------------------
# 场景 1：带宽受限 decode 吞吐
# ---------------------------------------------------------------------------

def scenario_bandwidth_decode() -> dict:
    """Q4 vs FP16 权重的 decode 上限，以及 MTP 投机解码的叠加收益。"""
    p = PHONE
    w_q4 = memory.weight_bytes(p["params"], p["q4_bits"], overhead=0.08)
    w_fp16 = memory.weight_bytes(p["params"], p["fp16_bits"], overhead=0.0)
    kv_bpt = memory.kv_bytes_per_token(p["layers"], p["kv_heads"], p["head_dim"], 2)
    t_q4 = memory.decode_tokens_per_s(p["bandwidth_gbs"], memory.decode_bytes_per_token(w_q4, kv_bpt), p["utilization"])
    t_fp16 = memory.decode_tokens_per_s(p["bandwidth_gbs"], memory.decode_bytes_per_token(w_fp16, kv_bpt), p["utilization"])
    ratio = t_q4 / t_fp16
    # MTP：端侧 draft 用小模型，成本比 0.15，接受率 0.75，γ=4
    mtp = speculative.speedup(0.75, 4, draft_cost_ratio=0.15)
    t_mtp = t_q4 * mtp

    print("=== 场景 1：带宽受限 decode 吞吐模型 ===")
    print(f"模型画像: 8B 参数, GQA(32 头/8 KV头), 带宽 {p['bandwidth_gbs']:.0f} GB/s, 利用率 {p['utilization']:.2f}")
    print(f"每 token 需读权重: Q4_K_M = {w_q4/1e9:.2f} GB, FP16 = {w_fp16/1e9:.2f} GB")
    print(f"decode 上限: Q4 = {t_q4:.2f} tok/s, FP16 = {t_fp16:.2f} tok/s (带宽相同, 比值 {ratio:.2f}x)")
    print(f"叠加 MTP(α=0.75, γ=4, draft 成本比 0.15, 加速比 {mtp:.2f}x): Q4+MTP ≈ {t_mtp:.2f} tok/s")
    return {"tok_q4": t_q4, "tok_fp16": t_fp16, "ratio": ratio, "mtp_speedup": mtp, "tok_mtp": t_mtp}


# ---------------------------------------------------------------------------
# 场景 2：KV cache 容量规划
# ---------------------------------------------------------------------------

def scenario_kv_capacity() -> dict:
    """8 GiB 统一内存下，权重 + KV 预算决定的最大上下文长度。"""
    p = PHONE
    w_gib = memory.weight_bytes(p["params"], p["q4_bits"], overhead=0.08) / memory.GIB
    plan = memory.quant_plan(p["layers"], p["kv_heads"], p["head_dim"],
                             p["total_gib"], p["reserve_gib"], w_gib)
    print("=== 场景 2：KV cache 容量与上下文规划 ===")
    print(f"设备: {p['total_gib']:.0f} GiB 统一内存, 保留 {p['reserve_gib']:.1f} GiB, "
          f"Q4_K_M 权重 {w_gib:.2f} GiB → KV 预算 {plan['budget_gib']:.2f} GiB")
    print(f"KV 每 token: FP16 = {plan['fp16']['bytes_per_token']} B, "
          f"INT8 = {plan['int8']['bytes_per_token']} B, INT4 = {plan['int4']['bytes_per_token']} B")
    for name in ("fp16", "int8", "int4"):
        print(f"最大上下文({name:>4} KV): {plan[name]['max_context']:>7,} tokens")
    return plan


# ---------------------------------------------------------------------------
# 场景 3：异构算子放置与回退
# ---------------------------------------------------------------------------

def _layer_ops(seq: int) -> list:
    """构造 prefill seq=512 的单层算子列表（Llama-3-8B 形状）。"""
    p = PHONE
    h, f, heads, kv, d = p["hidden"], p["ffn"], 32, p["kv_heads"], p["head_dim"]
    qkv_cols = h + 2 * kv * d
    return [
        Op("qkv_gemm", "matmul_int8", 2 * seq * h * qkv_cols, qkv_cols * h + seq * h * 2, seq * qkv_cols * 2),
        Op("rope", "elementwise", seq * h * 6, seq * h * 2 * 2, seq * h * 2 * 2),
        Op("softmax", "softmax", heads * seq * seq * 5, heads * seq * d * 4 * 2, heads * seq * d * 4),
        Op("attn_gemm", "matmul_fp16", 4 * seq * seq * h, seq * h * 2 * 2, seq * h * 2),
        Op("norm1", "norm", seq * h * 8, seq * h * 2 * 2, seq * h * 2 * 2),
        Op("gate_up", "matmul_int8", 2 * seq * h * 2 * f, 2 * f * h + seq * h * 2, seq * 2 * f * 2),
        Op("down", "matmul_int8", 2 * seq * f * h, f * h + seq * f * 2, seq * h * 2),
        Op("norm2", "norm", seq * h * 8, seq * h * 2 * 2, seq * h * 2 * 2),
    ]


def scenario_hetero_fallback() -> dict:
    """一层 prefill 在 NPU 优先 + 不支持算子回退 GPU/CPU 的时间线。"""
    p = PHONE
    npu = Device("NPU", tflops_fp16=22.0, tops_int8=45.0, bandwidth_gbs=136.0,
                 supported_ops=frozenset({"matmul_int8", "matmul_fp16", "elementwise"}))
    gpu = Device("GPU", tflops_fp16=6.0, tops_int8=8.0, bandwidth_gbs=68.0,
                 supported_ops=frozenset({"matmul_int8", "matmul_fp16", "elementwise", "softmax", "norm"}))
    cpu = Device("CPU", tflops_fp16=1.5, tops_int8=3.0, bandwidth_gbs=34.0,
                 supported_ops=frozenset({"matmul_int8", "matmul_fp16", "elementwise", "softmax", "norm"}),
                 is_fallback=True)
    devices = [npu, gpu, cpu]
    ops = _layer_ops(seq=512)
    placements, total = hetero.schedule_layer(ops, devices, fabric_gbs=p["fabric_gbs"], preferred=npu)

    print("=== 场景 3：异构算子放置与回退（seq=512 单层 prefill）===")
    print(f"{'算子':<12}{'设备':<6}{'计算(us)':>12}{'传输(us)':>12}")
    fb_transfer = 0.0
    for pl in placements:
        print(f"{pl.op:<12}{pl.device:<6}{pl.compute_us:>12.1f}{pl.transfer_us:>12.1f}"
              + (f"   (回退自 {pl.via})" if pl.via else ""))
        fb_transfer += pl.transfer_us
    print(f"单层总时延: {total:.1f} us, 回退传输税 {fb_transfer:.1f} us "
          f"({fb_transfer/total*100:.1f}%)")
    return {"total_us": total, "fallback_transfer_us": fb_transfer, "placements": placements}


# ---------------------------------------------------------------------------
# 场景 4：闪存流式加载
# ---------------------------------------------------------------------------

def scenario_mmap_streaming() -> dict:
    """同一模型文件：全量预载 vs 按需缺页 vs 预取窗口 vs 热子集。"""
    p = PHONE
    total_b = memory.weight_bytes(p["params"], p["q4_bits"], overhead=0.08)
    pages = streaming.page_count(total_b, p["page_bytes"])
    t_preload = streaming.preload_latency_us(total_b, p["bandwidth_gbs"])
    t_demand = streaming.mmap_latency_us(total_b, p["page_bytes"], p["bandwidth_gbs"], p["fault_us"])
    t_prefetch = streaming.mmap_latency_us(total_b, p["page_bytes"], p["bandwidth_gbs"], p["fault_us"],
                                           prefetch_pages=32)
    t_sparse = streaming.mmap_latency_us(total_b, p["page_bytes"], p["bandwidth_gbs"], p["fault_us"],
                                         access_fraction=0.30)
    t_sparse_pf = streaming.mmap_latency_us(total_b, p["page_bytes"], p["bandwidth_gbs"], p["fault_us"],
                                            access_fraction=0.30, prefetch_pages=32)

    print("=== 场景 4：闪存流式加载（mmap / 预取 / 热子集）===")
    print(f"模型文件 {total_b/1e9:.2f} GB, {pages:,} 页 x {p['page_bytes']//1024} KiB, "
          f"带宽 {p['bandwidth_gbs']:.0f} GB/s, 缺页开销 {p['fault_us']:.0f} us")
    print(f"全量预载(mlock):        {t_preload/1e6:>8.3f} s  (纯带宽项)")
    print(f"按需缺页(无预取):       {t_demand/1e6:>8.3f} s  (缺页项 {(t_demand-t_preload)/1e6:.3f} s)")
    print(f"预取窗口 32 页:         {t_prefetch/1e6:>8.3f} s  (缺页项 {(t_prefetch-t_preload)/1e6:.3f} s)")
    print(f"只访问 30% 页(热子集):   {t_sparse/1e6:>8.3f} s  (读入字节同比例下降)")
    print(f"30% 页 + 预取窗口 32:   {t_sparse_pf/1e6:>8.3f} s  (热子集 + readahead)")
    return {"preload_s": t_preload / 1e6, "demand_s": t_demand / 1e6,
            "prefetch_s": t_prefetch / 1e6, "sparse_s": t_sparse / 1e6,
            "sparse_prefetch_s": t_sparse_pf / 1e6, "pages": pages}


# ---------------------------------------------------------------------------
# 场景 5：LoRA 热切换
# ---------------------------------------------------------------------------

def scenario_lora_switch() -> dict:
    """rank=16 全层 adapter：热切换时延与合并方案的内存对比。"""
    p = PHONE
    adapter_b = lora.lora_adapter_bytes(p["layers"], 7, p["hidden"], rank=16)
    merged_b = lora.merged_adapter_bytes(p["layers"], 7, p["hidden"], p["ffn"])
    switch_us = lora.hot_switch_us(adapter_b, p["bandwidth_gbs"])
    ratio = lora.memory_ratio(adapter_b, merged_b)

    print("=== 场景 5：LoRA 热切换 vs 权重合并 ===")
    print(f"adapter(rank=16, 全 32 层 7 目标): {adapter_b/2**20:.1f} MiB")
    print(f"合并副本(全量 delta, fp16):       {merged_b/2**30:.2f} GiB")
    print(f"热切换一次: 卸载+加载 ≈ {switch_us - lora.SWITCH_FIXED_OVERHEAD_US:.1f} us "
          f"+ 固定开销 {lora.SWITCH_FIXED_OVERHEAD_US:.0f} us = {switch_us:.1f} us")
    print(f"内存比(热切换/合并): {ratio*100:.2f}% → 端侧 8 GiB 放不下 1 份合并副本,"
          f"但可同时驻留 {int((p['total_gib']-p['reserve_gib']-4.9)*1024/(adapter_b/2**20))} 个 adapter")
    return {"adapter_mib": adapter_b / 2**20, "merged_gib": merged_b / 2**30,
            "switch_us": switch_us, "ratio_pct": ratio * 100}


# ---------------------------------------------------------------------------
# 场景 6：端云混合路由
# ---------------------------------------------------------------------------

def scenario_edge_cloud_route() -> dict:
    """隐私/SLO/成本联合决策下的 4 个典型请求。"""
    device = routing.DeviceProfile(prefill_tps=180.0, decode_tps=13.0,
                                   derate_after_s=45.0, derate_factor=0.70)
    cloud = routing.CloudProfile(rtt_s=0.12, ttft_s=0.35, decode_tps=60.0,
                                 cost_per_1k_tokens=0.02, private_available=True)
    requests = [
        routing.Request("病历摘要", routing.CONFIDENTIAL, input_len=1024, output_len=256, latency_slo_s=120.0),
        routing.Request("闲聊问答", routing.PUBLIC, input_len=32, output_len=64, latency_slo_s=3.0),
        routing.Request("会议纪要", routing.INTERNAL, input_len=2048, output_len=256, latency_slo_s=60.0),
        routing.Request("长文续写", routing.PUBLIC, input_len=64, output_len=1024, latency_slo_s=30.0),
    ]
    print("=== 场景 6：端云混合路由决策 ===")
    print(f"{'请求':<10} {'隐私':<4} {'端侧(s)':>8} {'云端(s)':>8} {'决策':<14} 理由")
    results = {}
    for req in requests:
        r = routing.route(req, device, cloud)
        priv = {0: "公开", 1: "内部", 2: "机密"}[req.privacy]
        cloud_s = f"{r['cloud_s']:.2f}" if r["cloud_s"] != float("inf") else "--"
        print(f"{req.name:<10} {priv:<4} {r['device_s']:>8.2f} {cloud_s:>8} "
              f"{r['decision']:<14} {r['reason']}")
        results[req.name] = r
    return results


# ---------------------------------------------------------------------------

def run_demo() -> None:
    scenario_bandwidth_decode()
    print()
    scenario_kv_capacity()
    print()
    scenario_hetero_fallback()
    print()
    scenario_mmap_streaming()
    print()
    scenario_lora_switch()
    print()
    scenario_edge_cloud_route()


if __name__ == "__main__":
    run_demo()
