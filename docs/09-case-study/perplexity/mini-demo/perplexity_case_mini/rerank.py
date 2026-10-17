"""检索-重排-生成流水线中重排层的效果 / 延迟权衡。

对应主题章节：docs/09-case-study/perplexity/04（一次查询的生命线）。
语料为固定种子的确定性合成数据；检索与重排为带噪声的相关性估计。
"""

from __future__ import annotations

import numpy as np


def build_corpus(n_docs: int = 24, seed: int = 42) -> tuple[np.ndarray, list[str]]:
    """构造 (真实相关性, 文档 id) 列表。相关性确定，文档 id 逆序打散。"""
    rng = np.random.default_rng(seed)
    true_rel = np.round(rng.uniform(0.0, 1.0, size=n_docs), 4)
    ids = [f"doc-{i:02d}" for i in range(n_docs)]
    return true_rel, ids


def noisy_estimate(true_rel: np.ndarray, noise: float, seed: int) -> np.ndarray:
    """加性均匀噪声的相关性估计，截断到 [0, 1]。"""
    rng = np.random.default_rng(seed)
    est = true_rel + rng.uniform(-noise, noise, size=true_rel.shape)
    return np.clip(est, 0.0, 1.0)


def dcg(relevances: np.ndarray) -> float:
    """Discounted Cumulative Gain（一阶折扣）。"""
    if relevances.size == 0:
        return 0.0
    discounts = np.log2(np.arange(2, relevances.size + 2))
    return float(np.sum(relevances / discounts))


def ndcg_at_k(ranking: list[int], true_rel: np.ndarray, k: int) -> float:
    """ranking 为文档下标的有序列表。"""
    ideal = np.sort(true_rel)[::-1][:k]
    actual = true_rel[np.array(ranking[:k])] if ranking else np.array([])
    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg(actual) / ideal_dcg


def retrieve(true_rel: np.ndarray, top_k: int, noise: float, seed: int) -> list[int]:
    """第一阶段检索：按噪声估计取 top-k。"""
    est = noisy_estimate(true_rel, noise, seed)
    return list(np.argsort(-est)[:top_k])


def rerank(candidate_idx: list[int], true_rel: np.ndarray,
           noise: float, seed: int) -> list[int]:
    """第二阶段重排：对候选用更低噪声重新估计并排序。"""
    if not candidate_idx:
        return []
    est = noisy_estimate(true_rel[np.array(candidate_idx)], noise, seed)
    order = np.argsort(-est)
    return [candidate_idx[i] for i in order]


def pipeline_ndcg(true_rel: np.ndarray, top_k: int, k: int = 5,
                  retrieve_noise: float = 0.45, rerank_noise: float = 0.05,
                  use_rerank: bool = True, seed: int = 42) -> float:
    """完整流水线 NDCG@k。"""
    candidates = retrieve(true_rel, top_k, retrieve_noise, seed)
    if use_rerank:
        candidates = rerank(candidates, true_rel, rerank_noise, seed + 1)
    return ndcg_at_k(candidates, true_rel, k)


def latency_model(top_k: int, rerank_ms_per_doc: float = 2.0,
                  use_rerank: bool = True, base_retrieval_ms: float = 65.0) -> float:
    """延迟模型：检索基线（参照 Photon p99 ~65ms）+ 每候选重排开销。"""
    if not use_rerank:
        return base_retrieval_ms
    return base_retrieval_ms + top_k * rerank_ms_per_doc


def sweep_pool_size(true_rel: np.ndarray, pool_sizes: list[int],
                    k: int = 5, seed: int = 42) -> list[dict]:
    """扫描重排候选池大小：NDCG@k 与延迟的权衡曲线。"""
    rows = []
    for pool in pool_sizes:
        n = pipeline_ndcg(true_rel, top_k=pool, k=k, seed=seed)
        lat = latency_model(pool)
        rows.append({"pool": pool, "ndcg5": round(n, 4), "latency_ms": lat})
    return rows
