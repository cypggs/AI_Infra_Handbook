"""In-memory vector indexes for the vector_db_mini demo.

Three index types sharing one small API:

    index.add(vectors, ids=None, payloads=None)
    index.search(query, k, filter=None) -> list[SearchResult]

- FlatIndex      : brute force, the ground-truth baseline.
- IVFFlatIndex   : k-means inverted file, probe nprobe centroids at query time.
- HNSWIndex      : simplified HNSW — a single-layer proximity graph with
                   best-first beam search (M neighbors, ef / ef_construction).
                   Deterministic for a fixed insertion order.

All distances follow the convention "smaller is better" (see metric.py).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .metric import METRICS, pairwise_distance, top_k
from .quantize import _kmeans


@dataclass
class SearchResult:
    id: int
    distance: float
    payload: Dict[str, Any] = field(default_factory=dict)


class FlatIndex:
    """Brute-force exact search — the correctness baseline."""

    def __init__(self, dim: int, metric: str = "l2") -> None:
        if metric not in METRICS:
            raise ValueError(f"unknown metric {metric!r}")
        self.dim = dim
        self.metric = metric
        self._vectors: List[np.ndarray] = []
        self._ids: List[int] = []
        self._payloads: List[Dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._ids)

    def add(
        self,
        vectors: np.ndarray,
        ids: Optional[List[int]] = None,
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        v = np.asarray(vectors, dtype=np.float64)
        if v.ndim == 1:
            v = v.reshape(1, -1)
        if v.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {v.shape[1]}")
        n = len(v)
        if ids is None:
            start = (self._ids[-1] + 1) if self._ids else 0
            ids = list(range(start, start + n))
        if len(ids) != n:
            raise ValueError("ids length mismatch")
        if payloads is None:
            payloads = [{} for _ in range(n)]
        for row, i, p in zip(v, ids, payloads):
            self._vectors.append(row.copy())
            self._ids.append(int(i))
            self._payloads.append(dict(p))

    def search(
        self,
        query: np.ndarray,
        k: int,
        filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[SearchResult]:
        if not self._ids:
            return []
        q = np.asarray(query, dtype=np.float64).reshape(-1)
        dists = pairwise_distance(q, np.array(self._vectors), self.metric)[0]
        idx = top_k(dists, k=len(dists))
        out: List[SearchResult] = []
        for i in idx:
            if filter is not None and not filter(self._payloads[i]):
                continue
            out.append(
                SearchResult(self._ids[i], float(dists[i]), dict(self._payloads[i]))
            )
            if len(out) >= k:
                break
        return out


class IVFFlatIndex:
    """Inverted-file index: k-means coarse quantizer + exact scan inside cells."""

    def __init__(
        self,
        dim: int,
        metric: str = "l2",
        nlist: int = 8,
        nprobe: int = 2,
        seed: int = 0,
    ) -> None:
        if metric != "l2":
            # the demo keeps IVF on L2 for simplicity (real systems support all)
            raise ValueError("IVFFlatIndex demo supports metric='l2' only")
        self.dim = dim
        self.metric = metric
        self.nlist = nlist
        self.nprobe = nprobe
        self.seed = seed
        self._vectors: List[np.ndarray] = []
        self._ids: List[int] = []
        self._payloads: List[Dict[str, Any]] = []
        self._centroids: Optional[np.ndarray] = None
        self._lists: List[List[int]] = []

    def __len__(self) -> int:
        return len(self._ids)

    def add(
        self,
        vectors: np.ndarray,
        ids: Optional[List[int]] = None,
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        v = np.asarray(vectors, dtype=np.float64)
        if v.ndim == 1:
            v = v.reshape(1, -1)
        if v.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {v.shape[1]}")
        n = len(v)
        if ids is None:
            start = (self._ids[-1] + 1) if self._ids else 0
            ids = list(range(start, start + n))
        if payloads is None:
            payloads = [{} for _ in range(n)]
        for row, i, p in zip(v, ids, payloads):
            self._vectors.append(row.copy())
            self._ids.append(int(i))
            self._payloads.append(dict(p))
        self._centroids = None  # data changed, rebuild required

    def build(self) -> None:
        """Train the coarse quantizer and assign every vector to a cell."""
        data = np.array(self._vectors)
        if len(data) < self.nlist:
            raise ValueError("need at least nlist vectors to build")
        self._centroids, assign = _kmeans(
            data, self.nlist, iters=25, seed=self.seed
        )
        self._lists = [[] for _ in range(self.nlist)]
        for pos, cell in enumerate(assign):
            self._lists[cell].append(pos)

    @property
    def is_built(self) -> bool:
        return self._centroids is not None

    def search(
        self,
        query: np.ndarray,
        k: int,
        filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[SearchResult]:
        if self._centroids is None:
            raise RuntimeError("call build() before search()")
        q = np.asarray(query, dtype=np.float64).reshape(-1)
        cell_dists = pairwise_distance(q, self._centroids, self.metric)[0]
        probe_cells = top_k(cell_dists, k=self.nprobe)
        cand = [p for c in probe_cells for p in self._lists[c]]
        if not cand:
            return []
        cand_arr = np.array([self._vectors[p] for p in cand])
        dists = pairwise_distance(q, cand_arr, self.metric)[0]
        order = top_k(dists, k=len(dists))
        out: List[SearchResult] = []
        for o in order:
            pos = cand[o]
            if filter is not None and not filter(self._payloads[pos]):
                continue
            out.append(
                SearchResult(
                    self._ids[pos], float(dists[o]), dict(self._payloads[pos])
                )
            )
            if len(out) >= k:
                break
        return out


class HNSWIndex:
    """Simplified HNSW: a single-layer proximity graph.

    Real HNSW (Malkov & Yashunin) is a multi-layer skip-list of NSW graphs;
    this demo implements the core layer with best-first beam search:

    - insert: find the current ``ef_construction`` nearest nodes by beam
      search, keep the closest M as neighbors (mutual links are NOT added
      retroactively, keeping the build deterministic),
    - search: best-first expansion maintaining a result heap of size ef.

    Determinism: given the same insertion order and parameters, the graph
    is identical on every run (no unseeded randomness anywhere).
    """

    def __init__(
        self,
        dim: int,
        metric: str = "l2",
        M: int = 8,
        ef_construction: int = 32,
        ef: int = 16,
    ) -> None:
        if metric not in METRICS:
            raise ValueError(f"unknown metric {metric!r}")
        if ef < 1 or ef_construction < 1:
            raise ValueError("ef / ef_construction must be >= 1")
        self.dim = dim
        self.metric = metric
        self.M = M
        self.ef_construction = ef_construction
        self.ef = ef
        self._vectors: List[np.ndarray] = []
        self._ids: List[int] = []
        self._payloads: List[Dict[str, Any]] = []
        self._graph: List[List[int]] = []  # adjacency lists, node pos -> neighbors

    def __len__(self) -> int:
        return len(self._ids)

    @property
    def graph(self) -> List[List[int]]:
        return self._graph

    def add(
        self,
        vectors: np.ndarray,
        ids: Optional[List[int]] = None,
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        v = np.asarray(vectors, dtype=np.float64)
        if v.ndim == 1:
            v = v.reshape(1, -1)
        if v.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {v.shape[1]}")
        n = len(v)
        if ids is None:
            start = (self._ids[-1] + 1) if self._ids else 0
            ids = list(range(start, start + n))
        if payloads is None:
            payloads = [{} for _ in range(n)]
        for row, i, p in zip(v, ids, payloads):
            self._insert(row.copy(), int(i), dict(p))

    def _insert(self, vec: np.ndarray, vid: int, payload: Dict[str, Any]) -> None:
        pos = len(self._vectors)
        self._vectors.append(vec)
        self._ids.append(vid)
        self._payloads.append(payload)
        self._graph.append([])
        if pos == 0:
            return
        # beam search against the existing graph to find candidate neighbors
        cand = self._beam_search(vec, max(self.ef_construction, self.M + 1))
        chosen = cand[: self.M]
        self._graph[pos] = list(chosen)
        # deterministic stand-in for HNSW's mutual-link heuristic: also link
        # the new node from its chosen neighbors while their degree allows,
        # otherwise the earliest nodes would stay unreachable forever
        for nb in chosen:
            if len(self._graph[nb]) < 2 * self.M:
                self._graph[nb].append(pos)

    def _beam_search(self, query: np.ndarray, ef: int) -> List[int]:
        """Best-first beam search over the graph.

        Returns up to ef node positions sorted by distance to the query.
        """
        n = len(self._vectors)
        if n == 0:
            return []
        entry = 0
        entry_d = float(pairwise_distance(query, self._vectors[0], self.metric)[0, 0])
        visited = {entry}
        # candidate min-heap: (distance, pos)
        cand: List[tuple] = [(entry_d, entry)]
        # result max-heap (heapq min-heap on negated distance): (-d, pos)
        result: List[tuple] = [(-entry_d, entry)]
        while cand:
            d_cur, cur = heapq.heappop(cand)
            d_worst = -result[0][0]
            if d_cur > d_worst and len(result) >= ef:
                break
            for nb in self._graph[cur]:
                if nb in visited:
                    continue
                visited.add(nb)
                d_nb = float(
                    pairwise_distance(query, self._vectors[nb], self.metric)[0, 0]
                )
                if len(result) < ef or d_nb < d_worst:
                    heapq.heappush(cand, (d_nb, nb))
                    heapq.heappush(result, (-d_nb, nb))
                    if len(result) > ef:
                        heapq.heappop(result)
                    d_worst = -result[0][0]
        result.sort(key=lambda t: (-t[0], t[1]))  # by distance, then pos
        return [pos for _, pos in result]

    def search(
        self,
        query: np.ndarray,
        k: int,
        filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
        ef: Optional[int] = None,
    ) -> List[SearchResult]:
        q = np.asarray(query, dtype=np.float64).reshape(-1)
        ef_eff = max(ef or self.ef, k)
        positions = self._beam_search(q, ef_eff)
        out: List[SearchResult] = []
        for pos in positions:
            if filter is not None and not filter(self._payloads[pos]):
                continue
            d = float(pairwise_distance(q, self._vectors[pos], self.metric)[0, 0])
            out.append(SearchResult(self._ids[pos], d, dict(self._payloads[pos])))
            if len(out) >= k:
                break
        return out
