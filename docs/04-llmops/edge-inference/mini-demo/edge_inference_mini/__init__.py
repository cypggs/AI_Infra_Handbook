"""端侧与边缘推理基础设施 Mini Demo：纯 Python（仅 numpy）确定性模拟。

模块对照真实系统：

- ``clock``       —— 离散事件时钟（FakeClock），支撑异构调度的时间线模拟
- ``memory``      —— 带宽受限解码吞吐模型、权重/KV 容量与上下文规划
- ``hetero``      —— NPU/GPU/CPU 异构算子放置与回退（能力表 + 传输代价）
- ``streaming``   —— 闪存/磁盘 mmap 流式加载与预取窗口模型
- ``lora``        —— LoRA 热切换 vs 权重合并的内存/时延权衡
- ``speculative`` —— 投机解码 / MTP 的接受率-加速比解析模型
- ``routing``     —— 端-云（含隐私约束与热节流降额）混合路由决策
- ``demo``        —— 6 个端到端场景
"""

__version__ = "0.1.0"
