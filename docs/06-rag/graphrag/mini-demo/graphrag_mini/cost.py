"""确定性成本计量器：模拟 GraphRAG 流水线中 "LLM 调用" 的次数。

真实 GraphRAG 的成本几乎全部由 LLM token 构成（实体/关系抽取、
社区摘要、全局查询的 map-reduce）。本 demo 不调用任何真实 LLM，
用调用次数作为成本代理：一次抽取 = 1 次调用，一次社区摘要 = 1 次调用。
"""

from dataclasses import dataclass


@dataclass
class CostMeter:
    """记录模拟 LLM 调用次数，用于对比 "预计算全部社区摘要" 与
    "LazyGraphRAG 式延迟计算" 两种策略的成本差异。"""

    extract_calls: int = 0
    summary_calls: int = 0

    def charge_extract(self, n: int = 1) -> None:
        self.extract_calls += n

    def charge_summary(self, n: int = 1) -> None:
        self.summary_calls += n

    @property
    def total(self) -> int:
        return self.extract_calls + self.summary_calls
