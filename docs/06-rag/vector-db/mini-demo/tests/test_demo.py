import numpy as np
import pytest

from vector_db_mini.demo import run_demo, SCENARIOS


@pytest.fixture(scope="module")
def results():
    return run_demo()


def test_all_scenarios_present(results):
    names = [name for name, _ in SCENARIOS]
    assert list(results.keys()) == names
    assert len(results) == 6


def test_s1_baseline(results):
    s1 = results["S1 flat baseline"]
    assert s1["n_vectors"] == 2000
    assert s1["dim"] == 32
    assert s1["query_latency_ms"] > 0


def test_s2_ivf_recall_monotone(results):
    rows = results["S2 ivf vs flat"]["rows"]
    recalls = [r[1] for r in rows]
    assert recalls == sorted(recalls)
    assert recalls[-1] >= 0.9  # nprobe=8 should be near-exact on clusters
    assert all(0.0 <= r <= 1.0 for r in recalls)


def test_s3_hnsw_ef_tradeoff(results):
    s3 = results["S3 hnsw ef sweep"]
    rows = s3["rows"]
    recalls = [r[1] for r in rows]
    assert recalls == sorted(recalls)
    assert recalls[-1] >= 0.95
    assert s3["graph_edges"] > 0


def test_s4_quantization_ordering(results):
    s4 = results["S4 quantization"]
    # SQ(8bit) reconstructs better than PQ(4x16) on this data set
    assert s4["sq"]["rel_err"] < s4["pq"]["rel_err"]
    assert s4["sq"]["recall"] >= s4["pq"]["recall"]
    assert s4["sq"]["compression"] == pytest.approx(8 / 64)
    assert s4["pq"]["recall"] > 0.4  # honest PQ loss: tiny codebooks hurt recall


def test_s5_embedding_service(results):
    s5 = results["S5 embedding service"]
    assert s5["batches"] >= 3  # 10 docs / batch_size 4 -> 3 batches
    assert len(s5["flat_top"]) == 3
    assert len(s5["hnsw_top"]) == 3
    assert len(s5["zh_top"]) == 2
    # hnsw (exact-ish on 10 docs) should agree with flat on the top-1
    assert s5["hnsw_top"][0] == s5["flat_top"][0]


def test_s6_filter_trap(results):
    s6 = results["S6 filter trap"]
    assert s6["pre_recall"] == pytest.approx(1.0)
    assert s6["post_recall"] <= s6["pre_recall"]
    assert s6["post_filter_returned"] < 50  # some of top-50 filtered out
