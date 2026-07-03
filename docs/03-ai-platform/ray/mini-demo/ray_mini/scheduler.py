"""Hybrid scheduling policy (Ray's default).

Mirrors the whitepaper 'Default Hybrid Policy' + Scheduling docs:
  - prefer nodes that already hold the task's argument objects (locality)
  - within a top-k node group, favor low utilization (load balance)
  - switch from packing to spreading once critical utilization > spread_threshold
The demo reduces this to a deterministic scoring function.
"""
from __future__ import annotations

from typing import Optional, Collection

from .cluster import Cluster
from .model import Task


class HybridScheduler:
    def __init__(self, spread_threshold: float, top_k_fraction: float):
        self.spread_threshold = spread_threshold
        self.top_k_fraction = top_k_fraction

    def choose_node(
        self,
        cluster: Cluster,
        task: Task,
        arg_locations: dict[int, int],
        exclude_nodes: Optional[Collection[int]] = None,
    ) -> Optional[int]:
        """Pick a node for `task`. Returns node id or None if none can fit.

        ``arg_locations`` maps each arg ref id -> node id that holds a primary
        copy (for locality scoring).
        """
        exclude = set(exclude_nodes or ())
        candidates = [
            n for n in cluster.nodes.values()
            if n.id not in exclude and n.cpus_free >= task.num_cpus
        ]
        if not candidates:
            return None

        def locality_score(node_id: int) -> int:
            return sum(
                1 for arg in task.arg_refs
                if arg_locations.get(arg.id) == node_id
            )

        def utilization(node_id: int) -> float:
            node = cluster.nodes[node_id]
            return node.cpus_used / node.cpus_total if node.cpus_total else 1.0

        # Step 1: rank by locality (more local args first), tie-break lower util.
        ranked = sorted(
            candidates,
            key=lambda n: (-locality_score(n.id), utilization(n.id), n.id),
        )

        # Step 2: take top-k group.
        k = max(1, int(len(ranked) * self.top_k_fraction))
        top_k = ranked[:k]

        # Step 3: if the best candidate is already above spread_threshold on its
        # critical resource, spread: pick the least utilized node in top-k.
        best = top_k[0]
        if utilization(best.id) > self.spread_threshold:
            spread_pick = min(top_k, key=lambda n: (utilization(n.id), n.id))
            return spread_pick.id
        return best.id
