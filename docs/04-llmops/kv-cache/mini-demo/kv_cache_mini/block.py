"""Paged KV block 分配器：vLLM BlockTable 语义的极简版。

真实系统（vLLM v1 PagedAttention）把 KV cache 切成固定大小的 block，
用 BlockTable 把逻辑 token 位置映射到物理 block，从而：

1. 消除显存碎片（内部碎片最多一个 block）；
2. 通过引用计数支持 block 跨请求/跨分支共享（beam search、并行采样）；
3. 通过 copy-on-write 让共享分支各自修改；
4. 引用计数归零的 block 进入 LRU 逐出候选，供给 prefix cache 复用。

本模块不模拟真实 KV 张量内容，只模拟 block 元数据的生命周期。
"""

from __future__ import annotations


class OutOfBlocksError(RuntimeError):
    """空闲 block 耗尽且没有可逐出（引用计数为 0）的 block。"""


class BlockAllocator:
    """物理 block 池：分配 / 释放 / 共享 / COW / LRU 逐出。

    - ``alloc()`` 返回一个引用计数为 1 的 block；
    - ``free()`` 引用计数减一，归零后 block 变为「缓存中、可被逐出」；
    - ``share()`` 引用计数加一（用于 fork / 跨请求共享）；
    - ``cow()`` 写前复制：引用计数大于 1 时分配新 block 并转移引用；
    - 分配时若空闲池为空，逐出 LRU 的「引用计数为 0」block。
    """

    def __init__(self, num_blocks: int, block_size: int = 16) -> None:
        if num_blocks <= 0:
            raise ValueError("num_blocks must be positive")
        if block_size <= 0:
            raise ValueError("block_size must be positive")
        self.num_blocks = num_blocks
        self.block_size = block_size
        self._refcount: dict[int, int] = {}
        self._lru_tick: dict[int, int] = {}
        self._free_list: list[int] = list(range(num_blocks))
        self._tick = 0
        self.evictions = 0
        self.copies = 0  # COW 实际发生复制的次数

    # ------------------------------------------------------------------
    def _touch(self, block_id: int) -> None:
        self._tick += 1
        self._lru_tick[block_id] = self._tick

    @property
    def num_free(self) -> int:
        return len(self._free_list)

    @property
    def num_used(self) -> int:
        return len(self._refcount)

    @property
    def num_cached(self) -> int:
        """引用计数为 0、仍占用物理块、等待逐出的 block 数。"""
        return sum(1 for r in self._refcount.values() if r == 0)

    # ------------------------------------------------------------------
    def alloc(self) -> int:
        """分配一个 block，必要时触发 LRU 逐出。"""
        if not self._free_list:
            self._evict_one()
        block_id = self._free_list.pop()
        self._refcount[block_id] = 1
        self._touch(block_id)
        return block_id

    def free(self, block_id: int) -> None:
        """引用计数减一；归零后 block 保留为可复用缓存。"""
        if block_id not in self._refcount:
            raise KeyError(f"block {block_id} not allocated")
        if self._refcount[block_id] == 0:
            raise ValueError(f"block {block_id} already freed (refcount is 0)")
        self._refcount[block_id] -= 1
        self._touch(block_id)

    def share(self, block_id: int) -> None:
        """引用计数加一（fork / 共享语义）。"""
        if block_id not in self._refcount:
            raise KeyError(f"block {block_id} not allocated")
        self._refcount[block_id] += 1
        self._touch(block_id)

    def cow(self, block_id: int) -> int:
        """写前复制。独占则原地返回；共享则复制到新 block 并转移本引用。"""
        if block_id not in self._refcount:
            raise KeyError(f"block {block_id} not allocated")
        if self._refcount[block_id] > 1:
            self._refcount[block_id] -= 1
            new_id = self.alloc()
            self.copies += 1
            return new_id
        self._touch(block_id)
        return block_id

    def refcount(self, block_id: int) -> int:
        return self._refcount[block_id]

    # ------------------------------------------------------------------
    def _evict_one(self) -> int:
        candidates = [b for b, r in self._refcount.items() if r == 0]
        if not candidates:
            raise OutOfBlocksError(
                f"all {self.num_blocks} blocks are referenced; "
                "cannot evict (consider more blocks or smaller batch)"
            )
        victim = min(candidates, key=lambda b: self._lru_tick[b])
        del self._refcount[victim]
        del self._lru_tick[victim]
        self._free_list.append(victim)
        self.evictions += 1
        return victim


class BlockTable:
    """单个序列的逻辑 token 位置 → 物理 block 映射，支持 fork/COW。

    与 vLLM 的 ``BlockTable`` 对应：append 时按需申请新 block；
    ``fork()`` 复制映射表并对所有 block 加引用（写时复制）；
    ``write()`` 命中共享 block 时自动 COW。
    """

    def __init__(self, allocator: BlockAllocator) -> None:
        self.allocator = allocator
        self.blocks: list[int] = []

    @property
    def block_size(self) -> int:
        return self.allocator.block_size

    @property
    def capacity(self) -> int:
        """当前映射表可容纳的 token 数。"""
        return len(self.blocks) * self.block_size

    def __len__(self) -> int:
        return self.capacity

    def block_for_position(self, position: int) -> int:
        """逻辑 token 位置对应的物理 block id。"""
        if position < 0 or position >= self.capacity:
            raise IndexError(f"position {position} out of capacity {self.capacity}")
        return self.blocks[position // self.block_size]

    def _ensure_position(self, position: int) -> None:
        while position >= self.capacity:
            self.blocks.append(self.allocator.alloc())

    def append_tokens(self, num_tokens: int = 1) -> None:
        """为追加的 token 预留 block（假定从当前末尾连续追加）。"""
        if num_tokens <= 0:
            return
        last = 0 if not self.blocks else (len(self.blocks) - 1) * self.block_size
        self._ensure_position(last + num_tokens - 1)

    def write(self, position: int) -> int:
        """写 position 处的 KV；若该 block 被共享则先 COW。返回实际 block id。"""
        self._ensure_position(position)
        idx = position // self.block_size
        old = self.blocks[idx]
        new = self.allocator.cow(old)
        self.blocks[idx] = new
        return new

    def fork(self) -> "BlockTable":
        """派生共享本表全部 block 的子表（beam search / 并行采样语义）。"""
        child = BlockTable(self.allocator)
        for bid in self.blocks:
            self.allocator.share(bid)
        child.blocks = list(self.blocks)
        return child

    def release(self) -> None:
        """释放整条序列对所有 block 的引用。"""
        for bid in self.blocks:
            self.allocator.free(bid)
        self.blocks.clear()
