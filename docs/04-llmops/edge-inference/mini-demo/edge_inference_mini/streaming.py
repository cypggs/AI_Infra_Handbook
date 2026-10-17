"""闪存/磁盘流式加载（mmap + 预取）的解析模型。

对应 llama.cpp 的 mmap 加载（默认行为，权重不一次性读入，按需缺页）、
MLC 的分页加载与 Apple「LLM in a flash」（按神经元稀疏激活、只加载热子集）
这类技术。模型把「加载时延」拆成两部分：

- 带宽项：实际读入的字节数 / 带宽（可隐藏在小容量场景下被访问的子集内）；
- 缺页项：每次页缺失的固定开销（地址翻译、调度、TLB 抖动等经验常数）。

预取深度 P 表示流水线最多提前 P 页发起读取，深度之外的缺页被带宽项掩盖。
"""

from __future__ import annotations

import math


def page_count(total_bytes: float, page_bytes: int) -> int:
    if page_bytes <= 0:
        raise ValueError("page_bytes must be positive")
    if total_bytes <= 0:
        return 0
    return math.ceil(total_bytes / page_bytes)


def mmap_latency_us(total_bytes: float, page_bytes: int, bandwidth_gbs: float,
                    fault_overhead_us: float, access_fraction: float = 1.0,
                    prefetch_pages: int = 0) -> float:
    """mmap 流式加载的时延估算（微秒）。

    :param access_fraction: 实际被访问的页比例（稀疏激活/热子集 < 1.0）
    :param prefetch_pages: 预取窗口深度（页），相当于 OS readahead 窗口；
        0 表示纯按需缺页（每页同步缺页一次）；P>0 时缺页按窗口分批与读带宽
        重叠，暴露的缺页批数 = ceil(touched / P)
    """
    if bandwidth_gbs <= 0 or fault_overhead_us < 0:
        raise ValueError("invalid bandwidth/fault parameters")
    if not 0 < access_fraction <= 1:
        raise ValueError("access_fraction must be in (0, 1]")
    pages = page_count(total_bytes, page_bytes)
    touched = max(1, math.ceil(pages * access_fraction))
    read_us = touched * page_bytes / (bandwidth_gbs * 1e9) * 1e6
    if prefetch_pages <= 0:
        exposed_faults = touched
    else:
        exposed_faults = math.ceil(touched / prefetch_pages)
    return read_us + exposed_faults * fault_overhead_us


def preload_latency_us(total_bytes: float, bandwidth_gbs: float) -> float:
    """全量预载（mlock / 一次性 read）时延：纯带宽项。"""
    if total_bytes <= 0:
        return 0.0
    return total_bytes / (bandwidth_gbs * 1e9) * 1e6


def working_set_gib(total_gib: float, access_fraction: float) -> float:
    """给定访问比例下的工作集大小。"""
    if not 0 < access_fraction <= 1:
        raise ValueError("access_fraction must be in (0, 1]")
    return total_gib * access_fraction
