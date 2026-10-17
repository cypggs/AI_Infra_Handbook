"""LoRA 热切换 vs 权重合并：端侧多适配器管理的内存/时延权衡模型。

- 热切换（hot swap）：基座权重常驻，adapter 以低秩增量（A/B 两个矩阵）
  形式存于内存，切换 = 卸载旧 B/A + 加载新 B/A + 运行时重建 hook。
- 合并（merge）：把 delta 直接加到基座权重里，切换零成本，但每个 adapter
  都要保存一份「全量权重副本」，端侧内存几乎不可行。

模型参数全部显式给定，输出为解析解，完全确定。
"""

from __future__ import annotations

SWITCH_FIXED_OVERHEAD_US = 250.0  # 运行时重挂 hook、校验等固定开销


def lora_adapter_bytes(num_layers: int, num_targets: int, hidden: int, rank: int,
                       bytes_per_value: int = 2) -> int:
    """单个 LoRA adapter 的增量权重字节数：每层每目标两个 hidden×rank 矩阵。"""
    if min(num_layers, num_targets, hidden, rank) <= 0:
        raise ValueError("all dimensions must be positive")
    return num_layers * num_targets * 2 * hidden * rank * bytes_per_value


def merged_adapter_bytes(num_layers: int, num_targets: int, hidden: int, ffn_hidden: int,
                         bytes_per_value: int = 2) -> int:
    """一个「已合并 adapter」占用的全量副本字节数（delta 是 dense 的）。

    近似：每层的注意力 4 个 hidden×hidden 矩阵 + FFN 3 个 hidden×ffn 矩阵。
    """
    if min(num_layers, num_targets, hidden) <= 0 or ffn_hidden <= 0:
        raise ValueError("all dimensions must be positive")
    per_layer = (4 * hidden * hidden + 3 * hidden * ffn_hidden) * bytes_per_value
    return num_layers * per_layer


def hot_switch_us(adapter_bytes: int, bandwidth_gbs: float,
                  fixed_overhead_us: float = SWITCH_FIXED_OVERHEAD_US) -> float:
    """热切换一次 adapter 的时延：卸载+加载各占一半带宽 + 固定开销。"""
    if bandwidth_gbs <= 0:
        raise ValueError("bandwidth must be positive")
    move_us = 2.0 * adapter_bytes / (bandwidth_gbs * 1e9) * 1e6
    return move_us + fixed_overhead_us


def memory_ratio(adapter_b: int, merged_b: int) -> float:
    """热切换方案相对合并方案的内存占用比（<1 表示热切换省内存）。"""
    if merged_b <= 0:
        raise ValueError("merged bytes must be positive")
    return adapter_b / merged_b
