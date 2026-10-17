"""GPU/CPU/SSD 分层 KV 缓存模拟：迁移成本模型与命中收益。

真实系统代表：
- vLLM + LMCache：GPU → CPU DRAM → 本地 SSD / 远程存储；
- SGLang HiCache：L1 GPU → L2 CPU/NVMe → L3 远端（Mooncake Store 等）；
- NVIDIA Dynamo KV Block Manager：GPU → CPU → SSD → 对象存储。

分层缓存的核心权衡：慢层命中省下的 prefill 计算，必须大于
「读慢层 + 写快层」的迁移成本。本模块用确定性的秒级成本模型
量化这个权衡，并模拟 LRU 逐出与逐层降级（demote cascade）。
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class TierSpec:
    """单层缓存规格。

    - capacity_blocks: 该层最多容纳多少个 KV block；
    - read_cost_per_block / write_cost_per_block: 同步搬运一个 block 的
      秒级成本（真实系统里由带宽与延迟决定，如 HBM ~数 TB/s、
      PCIe ~数十 GB/s、NVMe ~数 GB/s、网络取决于 RDMA 带宽）。
    """

    name: str
    capacity_blocks: int
    read_cost_per_block: float
    write_cost_per_block: float


class TieredCache:
    """三层（GPU/CPU/SSD）KV 缓存，LRU 逐出，快层满时向慢层降级。"""

    GPU = "gpu"
    CPU = "cpu"
    SSD = "ssd"

    def __init__(
        self,
        gpu: TierSpec,
        cpu: TierSpec,
        ssd: TierSpec,
        prefill_cost_per_block: float = 0.02,
    ) -> None:
        specs = [gpu, cpu, ssd]
        if [s.name for s in specs] != [self.GPU, self.CPU, self.SSD]:
            raise ValueError("tiers must be gpu, cpu, ssd in that order")
        self.specs = {s.name: s for s in specs}
        # 每层一个 OrderedDict：key -> None；尾部为最热（MRU），头部为最冷（LRU）
        self._data: dict[str, OrderedDict] = {
            s.name: OrderedDict() for s in specs
        }
        # 成本模型参数：重新 prefill 一个 block 的秒级成本
        self.prefill_cost_per_block = prefill_cost_per_block
        # 统计
        self.hits: Counter = Counter()      # 各层命中次数
        self.misses: int = 0
        self.demotions: Counter = Counter() # 逐层降级次数（gpu->cpu, cpu->ssd, ssd->drop）
        self.total_cost_s: float = 0.0      # 所有 get/put 的同步迁移成本
        self.baseline_cost_s: float = 0.0   # 不缓存时的 prefill 总成本
        self.saved_prefill_s: float = 0.0   # 命中累计省下的 prefill 成本

    # ------------------------------------------------------------------
    def _locate(self, key: str) -> str | None:
        for name in (self.GPU, self.CPU, self.SSD):
            if key in self._data[name]:
                return name
        return None

    def _touch(self, tier: str, key: str) -> None:
        self._data[tier].move_to_end(key)

    def _insert(self, tier: str, key: str) -> None:
        """插入指定层（调用前须保证有空位）。"""
        self._data[tier][key] = None
        self._data[tier].move_to_end(key)

    def _evict_lru(self, tier: str) -> tuple[str, str]:
        """逐出 tier 的 LRU block，优先降级到下一层，底层则丢弃。

        返回 (被逐出的 key, 去向)。
        """
        key, _ = self._data[tier].popitem(last=False)
        order = [self.GPU, self.CPU, self.SSD]
        idx = order.index(tier)
        if idx == len(order) - 1:
            self.demotions[f"{tier}->drop"] += 1
            return key, "drop"
        nxt = order[idx + 1]
        if len(self._data[nxt]) >= self.specs[nxt].capacity_blocks:
            # 下一层也满：先递归逐出下一层，再降级
            self._evict_lru(nxt)
        self._insert(nxt, key)
        self.demotions[f"{tier}->{nxt}"] += 1
        return key, nxt

    def _make_room(self, tier: str) -> None:
        while len(self._data[tier]) >= self.specs[tier].capacity_blocks:
            self._evict_lru(tier)

    # ------------------------------------------------------------------
    def put(self, key: str) -> float:
        """写入一个 block 到 GPU 层，触发必要的降级。返回同步成本（秒）。"""
        loc = self._locate(key)
        if loc is not None:
            self._touch(loc, key)
            return 0.0
        self._make_room(self.GPU)
        self._insert(self.GPU, key)
        cost = self.specs[self.GPU].write_cost_per_block
        self.total_cost_s += cost
        return cost

    def get(self, key: str, promote: bool = True) -> tuple[bool, str | None, float]:
        """读取 block；命中慢层时按 promote 策略提升到 GPU。

        返回 (是否命中, 命中层名或 None, 同步成本秒)。
        """
        loc = self._locate(key)
        if loc is None:
            self.misses += 1
            self.baseline_cost_s += self.prefill_cost_per_block
            return False, None, 0.0
        self.hits[loc] += 1
        self.saved_prefill_s += self.prefill_cost_per_block
        cost = self.specs[loc].read_cost_per_block
        if promote and loc != self.GPU:
            self._data[loc].pop(key)
            self._make_room(self.GPU)
            self._insert(self.GPU, key)
            cost += self.specs[self.GPU].write_cost_per_block
        else:
            self._touch(loc, key)
        self.total_cost_s += cost
        return True, loc, cost

    # ------------------------------------------------------------------
    @property
    def hit_rate(self) -> float:
        total = sum(self.hits.values()) + self.misses
        return sum(self.hits.values()) / total if total else 0.0

    @property
    def savings_s(self) -> float:
        """相对「完全不缓存、全部重新 prefill」节省的时间：
        命中省下的 prefill 成本减去所有迁移成本。"""
        return self.saved_prefill_s - self.total_cost_s

    def occupancy(self) -> dict[str, int]:
        return {name: len(d) for name, d in self._data.items()}

    def simulate(self, keys: list[str]) -> dict:
        """回放访问序列，返回汇总统计。"""
        for k in keys:
            self.get(k)
        return {
            "hit_rate": round(self.hit_rate, 4),
            "hits": dict(self.hits),
            "misses": self.misses,
            "demotions": dict(self.demotions),
            "occupancy": self.occupancy(),
            "total_cost_s": round(self.total_cost_s, 6),
            "baseline_cost_s": round(self.baseline_cost_s, 6),
            "saved_prefill_s": round(self.saved_prefill_s, 6),
            "savings_s": round(self.savings_s, 6),
        }
