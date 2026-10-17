"""rerank 模块测试。"""

import numpy as np

from perplexity_case_mini import rerank
from perplexity_case_mini.demo import scenario_rerank


def test_corpus_deterministic():
    a, ids_a = rerank.build_corpus(seed=42)
    b, ids_b = rerank.build_corpus(seed=42)
    assert np.array_equal(a, b)
    assert ids_a == ids_b
    assert len(ids_a) == 24


def test_dcg_empty():
    assert rerank.dcg(np.array([])) == 0.0


def test_ndcg_ideal_is_one():
    true_rel, _ = rerank.build_corpus(seed=42)
    ideal = list(np.argsort(-true_rel))
    assert rerank.ndcg_at_k(ideal, true_rel, 5) == 1.0


def test_ndcg_bounded():
    true_rel, _ = rerank.build_corpus(seed=7)
    ranking = rerank.retrieve(true_rel, top_k=10, noise=0.45, seed=7)
    n = rerank.ndcg_at_k(ranking, true_rel, 5)
    assert 0.0 <= n <= 1.0


def test_retrieve_top_k():
    true_rel, _ = rerank.build_corpus(seed=42)
    assert len(rerank.retrieve(true_rel, top_k=8, noise=0.3, seed=1)) == 8


def test_rerank_preserves_candidate_set():
    true_rel, _ = rerank.build_corpus(seed=42)
    candidates = rerank.retrieve(true_rel, top_k=12, noise=0.3, seed=1)
    re = rerank.rerank(candidates, true_rel, noise=0.05, seed=2)
    assert sorted(re) == sorted(candidates)


def test_rerank_improves_ndcg():
    true_rel, _ = rerank.build_corpus(seed=42)
    no = rerank.pipeline_ndcg(true_rel, top_k=5, use_rerank=False, seed=42)
    yes = rerank.pipeline_ndcg(true_rel, top_k=24, use_rerank=True, seed=42)
    assert yes > no
    assert abs(no - 0.8777) < 1e-3
    assert abs(yes - 0.9985) < 1e-3


def test_latency_model_linear():
    assert rerank.latency_model(5, use_rerank=False) == 65.0
    assert rerank.latency_model(24) == 65.0 + 24 * 2.0
    assert rerank.latency_model(0) == 65.0


def test_sweep_monotonic_ndcg():
    true_rel, _ = rerank.build_corpus(seed=42)
    rows = rerank.sweep_pool_size(true_rel, [5, 8, 12, 16, 24])
    ndcgs = [r["ndcg5"] for r in rows]
    assert ndcgs == sorted(ndcgs)
    assert all(r["latency_ms"] == 65.0 + r["pool"] * 2.0 for r in rows)


def test_different_seeds_differ():
    true_rel, _ = rerank.build_corpus(seed=42)
    e1 = rerank.noisy_estimate(true_rel, 0.3, seed=1)
    e2 = rerank.noisy_estimate(true_rel, 0.3, seed=2)
    assert not np.array_equal(e1, e2)


def test_scenario_rerank_numbers():
    r = scenario_rerank()
    assert r["ndcg5_no_rerank_top5"] == 0.8777
    assert r["ndcg5_rerank_pool24"] == 0.9985
    assert r["latency_ms_rerank_pool24"] == 113.0
    assert r["curve"][-1] == {"pool": 24, "ndcg5": 0.9985, "latency_ms": 113.0}
