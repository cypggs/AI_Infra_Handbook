"""AI 编译器与 Kernel 生成 Mini Demo。

纯 Python + numpy，在 CPU 上模拟 AI 编译器的四个核心机制：
graph IR（graph.py）、算子融合（fusion.py）、auto-tune 与 cost model（tune.py）、
Triton-like tile kernel 语义（triton_like.py）。
"""

from .graph import Graph, Node, OpKind
from .fusion import FusionGroup, fuse, fused_count, explain_non_fusion
from .triton_like import FusedRowwiseKernel, KernelStats, TilingConfig, launch, run_tiled_matmul
from .tune import ScoredConfig, autotune, best_config, config_space, heuristic_cost

__all__ = [
    "Graph",
    "Node",
    "OpKind",
    "FusionGroup",
    "fuse",
    "fused_count",
    "explain_non_fusion",
    "FusedRowwiseKernel",
    "KernelStats",
    "TilingConfig",
    "launch",
    "run_tiled_matmul",
    "ScoredConfig",
    "autotune",
    "best_config",
    "config_space",
    "heuristic_cost",
]
