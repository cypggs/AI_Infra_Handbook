"""模型量化与压缩基础设施 Mini Demo。

纯 Python（仅依赖 numpy）模拟 LLM 量化工具链的四类核心机制：

- quantize.py   —— 对称/非对称、per-tensor/per-channel/group-wise 量化与误差度量
- gptq_like.py  —— 简化 OBS/GPTQ 风格逐列误差补偿量化（Hessian + Cholesky）
- smooth.py     —— SmoothQuant 风格「难度迁移」逐通道缩放
- kv_quant.py   —— KV cache 分 group 量化与注意力误差传播模拟
- demo.py       —— 6 个端到端场景

全部计算确定性可复现（固定随机种子，无 GPU 依赖）。
"""

__version__ = "0.1.0"
