"""kv_cache_mini: LLM 推理 KV Cache 管理迷你演示包。

模拟真实推理系统中的四类核心机制：

- block:      paged KV block 分配器（引用计数、copy-on-write、LRU 逐出）
- prefix:     radix tree 前缀匹配（跨请求 KV 共享、LRU 逐出）
- tier:       GPU/CPU/SSD 分层缓存（迁移成本模型、命中收益）
- migrate:    prefill/decode 分离下的 KV 传输调度（流水线重叠）
"""

from kv_cache_mini.block import BlockAllocator, BlockTable, OutOfBlocksError
from kv_cache_mini.prefix import RadixTree
from kv_cache_mini.tier import TierSpec, TieredCache
from kv_cache_mini.migrate import TransferEngine, PDScheduler

__all__ = [
    "BlockAllocator",
    "BlockTable",
    "OutOfBlocksError",
    "RadixTree",
    "TierSpec",
    "TieredCache",
    "TransferEngine",
    "PDScheduler",
]

__version__ = "0.1.0"
