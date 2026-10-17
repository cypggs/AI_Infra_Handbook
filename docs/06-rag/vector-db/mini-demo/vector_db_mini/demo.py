"""End-to-end scenarios for the vector_db_mini demo.

Run with:  python -m vector_db_mini.demo

Each scenario prints a section and returns a small results dict; the
collected dicts are returned by run_demo() so tests can assert on them.
All datasets are generated with fixed seeds, so recalls / errors are
reproducible; only wall-clock latencies vary between runs.
"""

from __future__ import annotations

import time
from typing import Dict, List

import numpy as np

from .embed import ToyEmbeddingServer, demo_documents
from .index import FlatIndex, HNSWIndex, IVFFlatIndex
from .metric import pairwise_distance
from .quantize import ProductQuantizer, ScalarQuantizer


def _synthetic_dataset(
    n: int = 2000,
    dim: int = 32,
    n_clusters: int = 16,
    seed: int = 42,
) -> tuple:
    """Clustered synthetic vectors: easy for ANN, hard enough to be interesting."""
    rng = np.random.RandomState(seed)
    centers = rng.randn(n_clusters, dim) * 3.0
    labels = rng.randint(0, n_clusters, size=n)
    vectors = centers[labels] + rng.randn(n, dim)
    return vectors, labels


def _recall_at_k(index, flat: FlatIndex, queries: np.ndarray, k: int = 10) -> float:
    hits = 0
    total = 0
    for q in queries:
        truth = {r.id for r in flat.search(q, k)}
        got = {r.id for r in index.search(q, k)}
        hits += len(truth & got)
        total += k
    return hits / total


def _bench(fn, repeat: int = 3) -> float:
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, (time.perf_counter() - t0) * 1000.0)
    return best


def scenario_flat_baseline() -> Dict:
    """S1: exact brute-force baseline on the synthetic dataset."""
    vectors, labels = _synthetic_dataset()
    flat = FlatIndex(dim=vectors.shape[1], metric="l2")
    flat.add(vectors)
    queries = vectors[:20]
    ms = _bench(lambda: [flat.search(q, 10) for q in queries]) / len(queries)
    result = {
        "n_vectors": len(flat),
        "dim": vectors.shape[1],
        "query_latency_ms": ms,
        "sample_label": int(labels[0]),
    }
    print("[S1] FlatIndex exact search")
    print(f"     n={result['n_vectors']} dim={result['dim']} "
          f"avg latency {ms:.3f} ms/query")
    return result


def scenario_ivf_vs_flat() -> Dict:
    """S2: IVFFlat recall/latency vs brute force, and the nprobe trade-off."""
    vectors, _ = _synthetic_dataset()
    flat = FlatIndex(dim=vectors.shape[1], metric="l2")
    flat.add(vectors)
    queries = vectors[:20]
    rows = []
    for nprobe in (1, 2, 4, 8):
        ivf = IVFFlatIndex(dim=vectors.shape[1], nlist=16, nprobe=nprobe, seed=0)
        ivf.add(vectors)
        ivf.build()
        recall = _recall_at_k(ivf, flat, queries)
        ms = _bench(lambda: [ivf.search(q, 10) for q in queries]) / len(queries)
        rows.append((nprobe, recall, ms))
    print("[S2] IVFFlatIndex vs FlatIndex (nlist=16)")
    for nprobe, recall, ms in rows:
        print(f"     nprobe={nprobe:<2} recall@10={recall:.3f}  {ms:.3f} ms/query")
    return {"rows": rows}


def scenario_hnsw_ef_sweep() -> Dict:
    """S3: simplified HNSW — recall climbs with ef, latency climbs too."""
    vectors, _ = _synthetic_dataset()
    dim = vectors.shape[1]
    flat = FlatIndex(dim=dim, metric="l2")
    flat.add(vectors)
    hnsw = HNSWIndex(dim=dim, metric="l2", M=8, ef_construction=32)
    hnsw.add(vectors)  # build is online: one insert at a time
    queries = vectors[:20]
    rows = []
    for ef in (4, 8, 16, 32, 64):
        hits, total = 0, len(queries) * 10
        def run():
            nonlocal hits
            hits = 0
            for q in queries:
                truth = {r.id for r in flat.search(q, 10)}
                got = {r.id for r in hnsw.search(q, 10, ef=ef)}
                hits += len(truth & got)
        ms = _bench(run) / len(queries)
        rows.append((ef, hits / total, ms))
    print("[S3] HNSWIndex ef sweep (M=8, ef_construction=32)")
    for ef, recall, ms in rows:
        print(f"     ef={ef:<3} recall@10={recall:.3f}  {ms:.3f} ms/query")
    return {"rows": rows, "graph_edges": sum(len(g) for g in hnsw.graph)}


def scenario_quantization() -> Dict:
    """S4: SQ / PQ compression ratios and recall on quantized reconstruction."""
    vectors, _ = _synthetic_dataset()
    dim = vectors.shape[1]
    flat = FlatIndex(dim=dim, metric="l2")
    flat.add(vectors)
    queries = vectors[:20]

    sq = ScalarQuantizer(bits=8).fit(vectors)
    sq_vecs = sq.decode(sq.encode(vectors))
    sq_err = float(np.linalg.norm(sq_vecs - vectors) / np.linalg.norm(vectors))
    sq_flat = FlatIndex(dim=dim, metric="l2")
    sq_flat.add(sq_vecs)

    # tiny demo codebooks (k=128) already show PQ's honest recall loss vs SQ
    pq = ProductQuantizer(m=8, k=128, seed=0).fit(vectors)
    pq_vecs = pq.decode(pq.encode(vectors))
    pq_err = float(np.linalg.norm(pq_vecs - vectors) / np.linalg.norm(vectors))
    pq_flat = FlatIndex(dim=dim, metric="l2")
    pq_flat.add(pq_vecs)

    def recall_of(idx) -> float:
        hits, total = 0, 0
        for q in queries:
            truth = {r.id for r in flat.search(q, 10)}
            got = {r.id for r in idx.search(q, 10)}
            hits += len(truth & got)
            total += 10
        return hits / total

    result = {
        "sq": {"compression": sq.compression_ratio(dim), "rel_err": sq_err,
               "recall": recall_of(sq_flat)},
        "pq": {"compression": pq.compression_ratio(), "rel_err": pq_err,
               "recall": recall_of(pq_flat)},
    }
    print("[S4] Quantization (vs float64 baseline)")
    for name, r in result.items():
        print(f"     {name.upper()}: ratio={r['compression']:.4f} "
              f"rel_err={r['rel_err']:.4f} recall@10={r['recall']:.3f}")
    return result


def scenario_embedding_service() -> Dict:
    """S5: toy embedding service -> HNSW retrieval, mimicking a RAG stack."""
    server = ToyEmbeddingServer(dim=256, normalize_embeddings=True, batch_size=4)
    docs = demo_documents()
    texts = [d["text"] for d in docs]
    vecs = server.encode(texts)
    dim = vecs.shape[1]
    flat = FlatIndex(dim=dim, metric="cosine")
    flat.add(vecs, ids=[d["id"] for d in docs],
             payloads=[{"lang": d["lang"], "category": d["category"]} for d in docs])
    hnsw = HNSWIndex(dim=dim, metric="cosine", M=4, ef_construction=16)
    hnsw.add(vecs, ids=[d["id"] for d in docs])

    query = "how does hnsw vector search work"
    qv = server.encode(query)
    flat_hits = flat.search(qv, 3)
    hnsw_hits = hnsw.search(qv, 3, ef=16)

    zh_query = "向量 量化 压缩 内存"
    zh_qv = server.encode(zh_query)
    zh_hits = flat.search(zh_qv, 2)

    print("[S5] ToyEmbeddingServer -> cosine retrieval")
    print(f"     server batches served: {server.batches_served} "
          f"(batch_size={server.batch_size})")
    print(f"     EN query top3 (flat): {[r.id for r in flat_hits]}")
    print(f"     EN query top3 (hnsw): {[r.id for r in hnsw_hits]}")
    print(f"     ZH query top2 (flat): {[r.id for r in zh_hits]}")
    return {
        "batches": server.batches_served,
        "flat_top": [r.id for r in flat_hits],
        "hnsw_top": [r.id for r in hnsw_hits],
        "zh_top": [r.id for r in zh_hits],
    }


def scenario_filter_trap() -> Dict:
    """S6: post-filtering trap — top-k then filter can return far fewer than k."""
    vectors, _ = _synthetic_dataset()
    payloads = [{"color": "red" if i % 10 < 9 else "blue"} for i in range(len(vectors))]
    dim = vectors.shape[1]

    flat = FlatIndex(dim=dim, metric="l2")
    flat.add(vectors, payloads=payloads)

    want_blue = lambda p: p["color"] == "blue"
    q = vectors[5]

    # wrong: take top-50 globally, then keep blue ones
    post = [r for r in flat.search(q, 50) if want_blue(r.payload)]
    # right: filter-aware scan (the demo flat index applies the predicate
    # during the scan, i.e. pre-filtering)
    pre = flat.search(q, 10, filter=want_blue)
    # ground truth for blue-only
    blue_positions = [i for i, p in enumerate(payloads) if p["color"] == "blue"]
    blue_arr = np.array([flat._vectors[i] for i in blue_positions])
    dists = pairwise_distance(q, blue_arr, "l2")[0]
    truth_ids = {flat._ids[blue_positions[i]] for i in np.argsort(dists, kind="stable")[:10]}

    post_ids = {r.id for r in post[:10]}
    pre_ids = {r.id for r in pre}
    result = {
        "selectivity": 0.1,
        "post_filter_returned": len(post),
        "post_recall": len(post_ids & truth_ids) / 10.0,
        "pre_recall": len(pre_ids & truth_ids) / 10.0,
    }
    print("[S6] Filter trap (blue selectivity ~10%)")
    print(f"     post-filter(top-50 then keep blue): {result['post_filter_returned']} "
          f"hits, recall@10={result['post_recall']:.3f}")
    print(f"     pre-filter(scan with predicate):    recall@10={result['pre_recall']:.3f}")
    return result


SCENARIOS = [
    ("S1 flat baseline", scenario_flat_baseline),
    ("S2 ivf vs flat", scenario_ivf_vs_flat),
    ("S3 hnsw ef sweep", scenario_hnsw_ef_sweep),
    ("S4 quantization", scenario_quantization),
    ("S5 embedding service", scenario_embedding_service),
    ("S6 filter trap", scenario_filter_trap),
]


def run_demo() -> Dict[str, Dict]:
    print("=" * 60)
    print("vector_db_mini demo — tiny vector search stack")
    print("=" * 60)
    results: Dict[str, Dict] = {}
    for name, fn in SCENARIOS:
        results[name] = fn()
        print()
    print("Done. All scenarios ran on CPU with fixed-seed datasets.")
    return results


if __name__ == "__main__":
    run_demo()
