"""异构算子放置与回退：NPU/GPU/CPU 能力表 + 传输代价的最小调度模型。

真实系统里这一层由 ExecuTorch 的 backend delegate、ONNX Runtime 的
ExecutionProvider、llama.cpp 的 ggml backend 抽象或 CoreML 的 ANE/GPU
启发式共同承担。这里把它抽象成可测试的规则：

1. 每个算子声明类型与（计算量 FLOP、搬运字节数）；
2. 每台设备声明支持的算子类型与峰值（TOPS/TFLOPS、带宽）；
3. 算子时间 = max(计算时间, 访存时间)（roofline 单拐点近似）；
4. 首选设备不支持时沿回退链降级，并在跨设备时追加一次传输代价；
5. 同一设备上的算子串行执行，总时延用 FakeClock 顺序累加。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .clock import FakeClock


@dataclass(frozen=True)
class Device:
    name: str
    tflops_fp16: float          # FP16 峰值算力（TFLOPS）
    tops_int8: float            # INT8 峰值算力（TOPS）
    bandwidth_gbs: float        # 访存带宽（GB/s）
    supported_ops: frozenset   # 可原生执行的算子类型
    is_fallback: bool = False  # 是否为兜底设备（链的终点）

    def rate_flops(self, op_kind: str) -> Optional[float]:
        """该设备上 op_kind 的每秒 FLOP 速率；不支持返回 None。"""
        if op_kind not in self.supported_ops:
            return None
        if op_kind == "matmul_int8":
            return self.tops_int8 * 1e12
        if op_kind in ("matmul_fp16",):
            return self.tflops_fp16 * 1e12
        # 元素级/归约类算子按 FP16 速率的固定折扣折算（向量化程度低）
        return self.tflops_fp16 * 0.5 * 1e12


@dataclass(frozen=True)
class Op:
    name: str
    kind: str            # matmul_int8 / matmul_fp16 / elementwise / softmax / norm
    flops: float         # FLOP
    bytes_in: float      # 输入字节（含要读取的权重）
    bytes_out: float     # 输出字节


@dataclass
class Placement:
    op: str
    device: str
    compute_us: float
    transfer_us: float = 0.0
    via: str = ""        # 若发生回退，记录首选设备

    @property
    def total_us(self) -> float:
        return self.compute_us + self.transfer_us


def op_time_us(op: Op, dev: Device) -> float:
    """单算子在单设备上的 roofline 时间（微秒）：max(计算, 访存)。"""
    rate = dev.rate_flops(op.kind)
    if rate is None:
        raise ValueError(f"device {dev.name} does not support {op.kind}")
    t_compute = op.flops / rate * 1e6
    t_memory = (op.bytes_in + op.bytes_out) / (dev.bandwidth_gbs * 1e9) * 1e6
    return max(t_compute, t_memory)


def place_op(op: Op, devices: List[Device], fabric_gbs: float = 60.0,
             preferred: Optional[Device] = None) -> Placement:
    """为一个算子选设备：优先 preferred，否则选时间最短的可用设备。

    回退时把输出（+输入，若输入在别台设备上则近似全量）经统一内存 fabric
    搬一次的代价计入 transfer_us。
    """
    if not devices:
        raise ValueError("no devices provided")
    candidates = sorted(
        devices, key=lambda d: op_time_us(op, d) if op.kind in d.supported_ops else float("inf")
    )
    chosen: Optional[Device] = None
    for d in candidates:
        if op.kind in d.supported_ops:
            chosen = d
            break
    if chosen is None:
        raise ValueError(f"no device supports {op.kind}")
    if preferred is not None and op.kind in preferred.supported_ops:
        chosen = preferred if op_time_us(op, preferred) <= op_time_us(op, chosen) * 1.5 else chosen
    via = ""
    transfer_us = 0.0
    if preferred is not None and chosen.name != preferred.name:
        via = preferred.name
        moved = op.bytes_in + op.bytes_out
        transfer_us = moved / (fabric_gbs * 1e9) * 1e6
    return Placement(op.name, chosen.name, op_time_us(op, chosen), transfer_us, via)


def schedule_layer(ops: List[Op], devices: List[Device], fabric_gbs: float = 60.0,
                   preferred: Optional[Device] = None, clock: Optional[FakeClock] = None
                   ) -> Tuple[List[Placement], float]:
    """把一个层（算子列表）按序放到设备上，返回放置表与总时延（微秒）。"""
    clock = clock or FakeClock()
    placements: List[Placement] = []
    start = clock.now_us
    end = start
    for op in ops:
        p = place_op(op, devices, fabric_gbs, preferred)
        end += p.total_us  # 同一设备/队列上串行：结束时间逐个累加
        clock.schedule(end, f"{op.name}@{p.device}")
        placements.append(p)
    clock.run()
    return placements, clock.now_us - start


def fallback_tax(placements: List[Placement]) -> float:
    """回退带来的额外开销占总时延的比例（0~1）。"""
    total = sum(p.total_us for p in placements)
    if total <= 0:
        return 0.0
    fallback = sum(p.transfer_us for p in placements)
    # 回退算子在兜底设备上的计算时间也算隐性税：用 via 非空标记
    return fallback / total
