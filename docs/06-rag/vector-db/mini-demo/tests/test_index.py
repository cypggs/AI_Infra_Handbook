import numpy as np
import pytest

from vector_db_mini.index import FlatIndex, HNSWIndex, IVFFlatIndex


@pytest.fixture
def data():
    rng = np.random.RandomState(42)
    centers = rng.randn(8, 16) * 3.0
    labels = rng.randint(0, 8, size=400)
    return centers[labels] + rng.randn(400, 16)


@pytest.fixture
def flat(data):
    idx = FlatIndex(dim=16, metric="l2")
    idx.add(data)
    return idx


class TestFlatIndex:
    def test_exact_top_k(self, flat, data):
        q = data[10]
        hits = flat.search(q, 5)
        assert len(hits) == 5
        assert hits[0].id == 10  # nearest to itself
        assert hits[0].distance == pytest.approx(0.0)

    def test_top_k_ordered_by_distance(self, flat, data):
        q = data[0]
        hits = flat.search(q, 10)
        ds = [h.distance for h in hits]
        assert ds == sorted(ds)

    def test_custom_ids(self, data):
        idx = FlatIndex(dim=16)
        idx.add(data[:5], ids=[100 + i for i in range(5)])
        hits = idx.search(data[2], 1)
        assert hits[0].id == 102

    def test_auto_ids_are_sequential_across_adds(self, data):
        idx = FlatIndex(dim=16)
        idx.add(data[:5])
        idx.add(data[5:7])
        assert [i for i in idx._ids] == list(range(7))

    def test_payload_filter(self, data):
        idx = FlatIndex(dim=16)
        payloads = [{"g": "even" if i % 2 == 0 else "odd"} for i in range(20)]
        idx.add(data[:20], payloads=payloads)
        hits = idx.search(data[0], 3, filter=lambda p: p["g"] == "odd")
        assert len(hits) == 3
        assert all(h.payload["g"] == "odd" for h in hits)

    def test_dim_mismatch_raises(self, flat):
        with pytest.raises(ValueError):
            flat.add(np.zeros((2, 8)))

    def test_empty_index_returns_empty(self):
        idx = FlatIndex(dim=4)
        assert idx.search(np.zeros(4), 5) == []

    def test_cosine_metric(self, data):
        idx = FlatIndex(dim=16, metric="cosine")
        idx.add(data)
        hits = idx.search(data[3], 1)
        assert hits[0].id == 3


class TestIVFFlatIndex:
    def test_requires_build(self, data):
        idx = IVFFlatIndex(dim=16, nlist=4)
        idx.add(data[:20])
        with pytest.raises(RuntimeError):
            idx.search(data[0], 5)

    def test_recall_close_to_one_on_clusters(self, flat, data):
        idx = IVFFlatIndex(dim=16, nlist=8, nprobe=4, seed=0)
        idx.add(data)
        idx.build()
        assert idx.is_built
        hits, total = 0, 0
        for q in data[:20]:
            truth = {r.id for r in flat.search(q, 10)}
            got = {r.id for r in idx.search(q, 10)}
            hits += len(truth & got)
            total += 10
        assert hits / total >= 0.9

    def test_more_probes_never_hurt_recall(self, flat, data):
        recalls = []
        for nprobe in (1, 2, 4, 8):
            idx = IVFFlatIndex(dim=16, nlist=8, nprobe=nprobe, seed=0)
            idx.add(data)
            idx.build()
            hits, total = 0, 0
            for q in data[:10]:
                truth = {r.id for r in flat.search(q, 10)}
                got = {r.id for r in idx.search(q, 10)}
                hits += len(truth & got)
                total += 10
            recalls.append(hits / total)
        assert recalls == sorted(recalls)

    def test_invalid_metric_rejected(self):
        with pytest.raises(ValueError):
            IVFFlatIndex(dim=16, metric="cosine")

    def test_add_invalidates_build(self, data):
        idx = IVFFlatIndex(dim=16, nlist=4)
        idx.add(data[:50])
        idx.build()
        assert idx.is_built
        idx.add(data[50:60])
        assert not idx.is_built

    def test_lists_cover_all_vectors(self, data):
        idx = IVFFlatIndex(dim=16, nlist=8, seed=0)
        idx.add(data)
        idx.build()
        assert sum(len(l) for l in idx._lists) == len(data)


class TestHNSWIndex:
    def test_nearest_is_self(self, data):
        idx = HNSWIndex(dim=16, M=8, ef=16)
        idx.add(data)
        hits = idx.search(data[7], 3, ef=32)
        assert hits[0].id == 7

    def test_recall_at_least_095(self, flat, data):
        idx = HNSWIndex(dim=16, M=8, ef_construction=32)
        idx.add(data)
        hits, total = 0, 0
        for q in data[:20]:
            truth = {r.id for r in flat.search(q, 10)}
            got = {r.id for r in idx.search(q, 10, ef=32)}
            hits += len(truth & got)
            total += 10
        assert hits / total >= 0.95

    def test_higher_ef_improves_or_keeps_recall(self, flat, data):
        idx = HNSWIndex(dim=16, M=8, ef_construction=32)
        idx.add(data)
        recalls = []
        for ef in (4, 8, 16, 32):
            hits, total = 0, 0
            for q in data[:10]:
                truth = {r.id for r in flat.search(q, 10)}
                got = {r.id for r in idx.search(q, 10, ef=ef)}
                hits += len(truth & got)
                total += 10
            recalls.append(hits / total)
        assert recalls == sorted(recalls)

    def test_deterministic_construction(self, data):
        a = HNSWIndex(dim=16, M=8)
        a.add(data)
        b = HNSWIndex(dim=16, M=8)
        b.add(data)
        assert a.graph == b.graph

    def test_degree_bounded(self, data):
        idx = HNSWIndex(dim=16, M=4)
        idx.add(data)
        # new nodes keep <= M links; older nodes accept up to 2M reverse links
        assert all(len(g) <= 8 for g in idx.graph)

    def test_ef_capped_at_k(self, data):
        idx = HNSWIndex(dim=16, M=4, ef=1)
        idx.add(data)
        hits = idx.search(data[0], 5)
        assert len(hits) == 5  # ef_eff = max(ef, k)

    def test_filter_search(self, data):
        idx = HNSWIndex(dim=16)
        payloads = [{"t": i % 3} for i in range(60)]
        idx.add(data[:60], payloads=payloads)
        hits = idx.search(data[1], 2, filter=lambda p: p["t"] == 0)
        assert len(hits) == 2
        assert all(h.payload["t"] == 0 for h in hits)

    def test_cosine_metric(self, data):
        idx = HNSWIndex(dim=16, metric="cosine")
        idx.add(data)
        hits = idx.search(data[5], 1, ef=32)
        assert hits[0].id == 5

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            HNSWIndex(dim=16, ef=0)
        with pytest.raises(ValueError):
            HNSWIndex(dim=16, metric="bogus")
