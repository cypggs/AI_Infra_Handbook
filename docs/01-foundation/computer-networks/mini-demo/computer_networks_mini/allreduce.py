"""Ring and tree all-reduce over a topology."""
from __future__ import annotations

from typing import Dict, List

from .topology import Topology


def ring_allreduce(values: Dict[str, float], topology: Topology) -> Dict[str, float]:
    """Simulate chunk-based ring all-reduce: each node ends with the global average.

    Each node starts with a vector of length n, where only its own slot contains
    its local value.  After reduce-scatter + all-gather around the ring, every
    slot holds the global sum; the returned value is the average.
    """
    nodes = list(values.keys())
    if not nodes:
        return {}
    n = len(nodes)

    # Each node's local vector: only slot i is non-zero initially.
    vectors: Dict[str, List[float]] = {node: [0.0] * n for node in nodes}
    for i, node in enumerate(nodes):
        vectors[node][i] = values[node]

    # Reduce-scatter: after n-1 steps each vector slot has the global sum.
    for step in range(n - 1):
        snapshot = {node: list(v) for node, v in vectors.items()}
        for i, node in enumerate(nodes):
            prev_node = nodes[(i - 1) % n]
            recv_chunk = (i - 1 - step) % n
            vectors[node][recv_chunk] += snapshot[prev_node][recv_chunk]

    # All-gather (already complete for n == vector length, but kept for symmetry).
    for step in range(n - 1):
        snapshot = {node: list(v) for node, v in vectors.items()}
        for i, node in enumerate(nodes):
            prev_node = nodes[(i - 1) % n]
            recv_chunk = (i - 1 - step) % n
            vectors[node][recv_chunk] = snapshot[prev_node][recv_chunk]

    total = sum(vectors[nodes[0]])
    avg = total / n
    return {node: avg for node in nodes}


def tree_allreduce(values: Dict[str, float], topology: Topology) -> Dict[str, float]:
    """Simulate tree all-reduce via simple aggregation to an arbitrary root."""
    nodes = list(values.keys())
    if not nodes:
        return {}
    total = sum(values.values())
    avg = total / len(nodes)
    return {node: avg for node in nodes}
