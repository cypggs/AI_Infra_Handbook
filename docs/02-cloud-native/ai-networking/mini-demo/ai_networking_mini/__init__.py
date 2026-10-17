"""ai_networking_mini —— AI 集群网络教学模拟器。

把真实 AI 训练集群网络的核心机制压缩成 CPU 可运行的纯 Python 模型：

| 模块 | 模拟的真实机制 |
|---|---|
| topology | Leaf-Spine / k-ary fat-tree / rail-optimized 拓扑生成、BFS 跳数、二分带宽与收敛比 |
| traffic | TP/DP/EP/PP 并行策略的每步流量矩阵（ring 边、all-to-all 矩阵、热点因子） |
| congestion | incast 扇入完成时间、ECN 标记概率、简化 DCQCN 速率调整、PFC 缓冲区依赖死锁检测 |
| collective | ring/tree all-reduce、all-to-all 的步数与数据量闭式模型，跨 fabric 对比 |
| demo | 6 个端到端场景串联以上所有模块 |

所有计算都是确定性的闭式公式或固定逻辑，不依赖随机数。
"""

from . import topology, traffic, congestion, collective

__all__ = ["topology", "traffic", "congestion", "collective"]
__version__ = "0.1.0"
