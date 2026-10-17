"""端侧内存模型：带宽受限解码吞吐 + 权重/KV 容量与上下文规划。

核心事实（本模块把它变成可计算的公式）：

- decode 阶段每生成 1 个 token 都要把「本步参与计算的权重 + KV cache」
  从内存完整读一遍，算术强度极低，因此吞吐上限 ≈ 带宽 / 每 token 字节数。
- KV cache 每 token 字节数 = 2 (K,V) × 层数 × KV 头数 × head_dim × 每值字节数，
  GQA（分组查询注意力）把 KV 头数降到 4~8，是端侧长上下文的关键使能者。
"""

from __future__ import annotations

GIB = 1024**3


def weight_bytes(num_params: float, bits_per_weight: float, overhead: float = 0.05) -> int:
    """量化权重的存储字节数（含 scale/zero-point 等元数据开销）。

    :param num_params: 参数量（如 8e9 表示 8B 模型）
    :param bits_per_weight: 等效位宽（FP16=16，Q4_K 类混合量化约 4.8）
    :param overhead: 元数据开销比例，GGUF K-quant 类经验值 3%~8%
    """
    if bits_per_weight <= 0 or overhead < 0:
        raise ValueError("invalid quantization description")
    return int(num_params * bits_per_weight / 8 * (1.0 + overhead))


def kv_bytes_per_token(num_layers: int, kv_heads: int, head_dim: int, bytes_per_value: int = 2) -> int:
    """单个 token 的 KV cache 字节数（GQA/MQA 通过 kv_heads 体现）。"""
    if min(num_layers, kv_heads, head_dim, bytes_per_value) <= 0:
        raise ValueError("all dimensions must be positive")
    return 2 * num_layers * kv_heads * head_dim * bytes_per_value


def decode_bytes_per_token(weight_b: int, kv_bpt: int, context_len: int = 1) -> int:
    """decode 每步需搬运的字节数：权重全量 + 当前 KV 工作集。"""
    if weight_b <= 0 or kv_bpt < 0 or context_len < 1:
        raise ValueError("invalid decode description")
    return weight_b + kv_bpt * context_len


def decode_tokens_per_s(bandwidth_gbs: float, bytes_per_token: float, utilization: float = 0.85) -> float:
    """带宽受限 decode 吞吐上限（tok/s）。

    utilization 表示真实 kernel 对带宽的兑现比例（cache 命中、调度气泡、
    激活读写等都会让它低于 1.0；llama.cpp 类手写 kernel 经验值 0.7~0.9）。
    """
    if bandwidth_gbs <= 0 or bytes_per_token <= 0:
        raise ValueError("bandwidth and bytes must be positive")
    if not 0 < utilization <= 1:
        raise ValueError("utilization must be in (0, 1]")
    return bandwidth_gbs * 1e9 * utilization / bytes_per_token


def kv_budget_bytes(total_gib: float, reserve_gib: float, weights_gib: float) -> int:
    """扣掉 OS/运行时保留与权重后，留给 KV cache 的字节数。"""
    left = total_gib - reserve_gib - weights_gib
    if left <= 0:
        return 0
    return int(left * GIB)


def max_context_len(kv_budget_b: int, kv_bpt: int) -> int:
    """给定 KV 预算，可支撑的最大上下文长度（token 数）。"""
    if kv_bpt <= 0:
        raise ValueError("kv_bpt must be positive")
    return kv_budget_b // kv_bpt


def quant_plan(num_layers: int, kv_heads: int, head_dim: int, total_gib: float,
               reserve_gib: float, weights_gib: float) -> dict:
    """一次算出 FP16 / INT8 / INT4 三档 KV 量化下的上下文上限。"""
    budget = kv_budget_bytes(total_gib, reserve_gib, weights_gib)
    base = kv_bytes_per_token(num_layers, kv_heads, head_dim, 2)  # FP16 基准
    plan = {}
    for name, mult in (("fp16", 1.0), ("int8", 0.5), ("int4", 0.25)):
        bpt = int(base * mult)
        plan[name] = {"bytes_per_token": bpt, "max_context": max_context_len(budget, bpt)}
    plan["budget_gib"] = budget / GIB
    return plan
