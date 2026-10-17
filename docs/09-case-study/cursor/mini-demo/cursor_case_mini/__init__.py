"""Cursor 案例研究 Mini Demo：模拟可确证机制的纯 Python + numpy 包。

五个教学模块：
- indexing.py    代码库索引管道：chunk -> embed -> Merkle 增量更新 -> 向量检索
- latency.py     Tab 补全端到端延迟预算分解
- speculative.py Speculative Edits 命中率与加速比模型
- sandbox.py     后台 Agent 沙箱资源配额与调度
- economics.py   订阅制推理经济学：token 成本 vs 月费盈亏平衡
"""

__version__ = "0.1.0"
