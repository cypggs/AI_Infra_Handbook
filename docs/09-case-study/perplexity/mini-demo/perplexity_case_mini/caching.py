"""语义缓存与精确缓存的命中率 / 成本节省模拟。

对应主题章节：docs/09-case-study/perplexity/05-core-modules（缓存层）。
答案用"归一化查询串"代表；语义相似度用词袋向量余弦（确定性）。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


def normalize(query: str) -> str:
    """查询规范化：小写、去多余空白。"""
    return " ".join(query.strip().lower().split())


def query_vector(query: str) -> dict[str, float]:
    """词袋向量（去重计词频），作为语义相似度的确定性替代。"""
    vec: dict[str, float] = {}
    for tok in normalize(query).split():
        vec[tok] = vec.get(tok, 0.0) + 1.0
    return vec


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass
class CacheEntry:
    query: str
    answer: str
    stored_at: float
    vector: dict[str, float] = field(default_factory=dict)


class AnswerCache:
    """两层缓存：exact（规范化串完全匹配 + TTL）+ semantic（余弦相似度 >= 阈值）。"""

    def __init__(self, ttl_s: float = 3600.0, semantic_threshold: float = 0.90):
        self.ttl_s = ttl_s
        self.semantic_threshold = semantic_threshold
        self._exact: dict[str, CacheEntry] = {}
        self._semantic: list[CacheEntry] = []

    def _fresh(self, entry: CacheEntry, now: float) -> bool:
        return now - entry.stored_at <= self.ttl_s

    def get(self, query: str, now: float = 0.0) -> tuple[str | None, str]:
        """返回 (答案, 命中层级)；未命中返回 (None, 'miss')。"""
        key = normalize(query)
        entry = self._exact.get(key)
        if entry is not None and self._fresh(entry, now):
            return entry.answer, "exact"
        vec = query_vector(query)
        best: CacheEntry | None = None
        best_sim = 0.0
        for cand in self._semantic:
            if not self._fresh(cand, now):
                continue
            sim = cosine(vec, cand.vector)
            if sim > best_sim:
                best_sim = sim
                best = cand
        if best is not None and best_sim >= self.semantic_threshold:
            return best.answer, "semantic"
        return None, "miss"

    def put(self, query: str, answer: str, now: float = 0.0) -> None:
        key = normalize(query)
        entry = CacheEntry(query=key, answer=answer, stored_at=now,
                           vector=query_vector(query))
        self._exact[key] = entry
        self._semantic.append(entry)


def simulate_traffic(queries: list[tuple[str, float]],
                     answer_cost: float,
                     ttl_s: float = 3600.0,
                     semantic_threshold: float = 0.90) -> dict:
    """模拟一段确定性查询流。

    queries: [(查询文本, 到达时间戳)]；每次 miss 付出 answer_cost 美元。
    """
    cache = AnswerCache(ttl_s=ttl_s, semantic_threshold=semantic_threshold)
    n_exact = n_semantic = n_miss = 0
    cost = 0.0
    for query, now in queries:
        answer, layer = cache.get(query, now)
        if layer == "exact":
            n_exact += 1
        elif layer == "semantic":
            n_semantic += 1
        else:
            n_miss += 1
            cost += answer_cost
            cache.put(query, answer=f"A[{normalize(query)}]", now=now)
    n = len(queries)
    baseline = n * answer_cost
    return {
        "n_queries": n,
        "n_exact": n_exact,
        "n_semantic": n_semantic,
        "n_miss": n_miss,
        "exact_hit_rate": n_exact / n,
        "semantic_hit_rate": n_semantic / n,
        "total_hit_rate": (n_exact + n_semantic) / n,
        "cost_usd": cost,
        "baseline_cost_usd": baseline,
        "savings_pct": (1.0 - cost / baseline) * 100.0 if baseline else 0.0,
    }
