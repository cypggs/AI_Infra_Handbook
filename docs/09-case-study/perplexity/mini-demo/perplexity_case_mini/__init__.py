"""Perplexity 案例研究 Mini Demo：答案引擎推理经济学模拟器。

四个模块：
- routing:   模型路由与成本-质量权衡
- caching:   exact + 语义缓存
- streaming: TTFT 与流式感知延迟
- rerank:    检索-重排流水线的质量/延迟权衡
"""

from . import caching, rerank, routing, streaming  # noqa: F401

__all__ = ["caching", "rerank", "routing", "streaming"]
