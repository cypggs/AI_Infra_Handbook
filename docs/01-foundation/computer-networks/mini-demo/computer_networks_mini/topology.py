"""Simple weighted-graph topology for network simulation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class Topology:
    """Undirected weighted graph representing a network topology."""
    nodes: Set[str]
    links: Dict[Tuple[str, str], Dict[str, float]]

    def add_link(self, a: str, b: str, latency: float = 1.0, bandwidth: float = 1.0) -> None:
        self.nodes.add(a)
        self.nodes.add(b)
        self.links[(a, b)] = {"latency": latency, "bandwidth": bandwidth}
        self.links[(b, a)] = {"latency": latency, "bandwidth": bandwidth}

    def neighbors(self, node: str) -> List[str]:
        return [b for (a, b) in self.links if a == node]

    def latency(self, a: str, b: str) -> float:
        return self.links.get((a, b), {"latency": float("inf")})["latency"]

    def shortest_path(self, src: str, dst: str) -> List[str]:
        """Dijkstra shortest path."""
        import heapq
        dist: Dict[str, float] = {n: float("inf") for n in self.nodes}
        prev: Dict[str, str | None] = {n: None for n in self.nodes}
        dist[src] = 0.0
        heap: List[Tuple[float, str]] = [(0.0, src)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v in self.neighbors(u):
                nd = d + self.latency(u, v)
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        if dst not in dist or dist[dst] == float("inf"):
            return []
        path: List[str] = []
        cur: str | None = dst
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        return list(reversed(path))

    @classmethod
    def ring(cls, nodes: List[str]) -> "Topology":
        topo = cls(set(nodes), {})
        for i, node in enumerate(nodes):
            next_node = nodes[(i + 1) % len(nodes)]
            topo.add_link(node, next_node)
        return topo

    @classmethod
    def fat_tree_like(cls, leaves: List[str], spines: List[str]) -> "Topology":
        topo = cls(set(leaves) | set(spines), {})
        for leaf in leaves:
            for spine in spines:
                topo.add_link(leaf, spine, latency=1.0)
        return topo
