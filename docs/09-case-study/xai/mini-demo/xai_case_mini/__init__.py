"""xAI Colossus 超集群建设核心权衡模拟器。

纯 Python + numpy，CPU 可运行、完全确定性。模拟四个核心权衡：

- power.py    供电容量规划（电网 vs 燃气轮机 vs 训练功率曲线）
- network.py  单一大集群 vs 多园区拓扑的 AllReduce 通信模型（RoCE vs IB 效率假设）
- build.py    集群建设排程（并行工作流 + 关键路径分析，复现"122 天"式压缩）
- cooling.py  风冷 vs 液冷的机柜功率密度模型

运行演示::

    python -m xai_case_mini.demo
"""

from . import build, cooling, network, power

__all__ = ["build", "cooling", "network", "power"]
__version__ = "0.1.0"
