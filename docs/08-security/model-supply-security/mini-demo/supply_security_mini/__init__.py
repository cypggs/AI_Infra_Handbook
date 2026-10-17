"""Mini Demo：AI 供应链与模型安全最小闭环。

仅依赖 numpy（数值计算）与 Python 标准库（pickle/pickletools/hashlib/hmac/json）。
五个模块对应文档第 5 章的五条防线：

- pickle_scan：pickle 字节流 opcode 风险扫描 vs safetensors 安全加载对照
- signing：模型工件签名-验证链（merkle 清单 + HMAC 签名 + 篡改定位）
- mcp_integrity：MCP 工具清单完整性校验（hash 不符拒绝加载、描述投毒 diff）
- poisoning：训练数据投毒检测（canary 样本触发率）
- watermark：模型权重水印嵌入/抽取（确定性伪随机模式）
"""

from . import mcp_integrity, pickle_scan, poisoning, signing, watermark

__all__ = ["pickle_scan", "signing", "mcp_integrity", "poisoning", "watermark"]
__version__ = "0.1.0"
