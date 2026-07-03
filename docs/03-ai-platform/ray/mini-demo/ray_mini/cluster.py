"""Cluster and node resource accounting for the mini Ray simulator."""
from __future__ import annotations

from .model import Config
from .object_store import ObjectStore


class Node:
    """A single Ray node: CPU resources + object store."""

    def __init__(self, node_id: int, cpus_total: int, store_capacity: int, spill_threshold: float):
        self.id = node_id
        self.cpus_total = cpus_total
        self.cpus_used = 0
        self.store = ObjectStore(node_id, store_capacity, spill_threshold)

    @property
    def cpus_free(self) -> int:
        return self.cpus_total - self.cpus_used

    def allocate_cpu(self, n: int = 1) -> None:
        if n > self.cpus_free:
            raise RuntimeError(f"node {self.id}: cannot allocate {n} CPUs (free {self.cpus_free})")
        self.cpus_used += n

    def release_cpu(self, n: int = 1) -> None:
        self.cpus_used = max(0, self.cpus_used - n)

    def __repr__(self) -> str:
        return f"Node({self.id}, cpus={self.cpus_used}/{self.cpus_total})"


class Cluster:
    """A collection of Ray nodes."""

    def __init__(self, config: Config):
        self.config = config
        self.nodes: dict[int, Node] = {}
        for i in range(config.num_nodes):
            self.add_node(i)

    def add_node(self, node_id: int) -> Node:
        node = Node(
            node_id,
            self.config.cpus_per_node,
            self.config.object_store_capacity,
            self.config.object_spilling_threshold,
        )
        self.nodes[node_id] = node
        return node

    def remove_node(self, node_id: int) -> Node:
        return self.nodes.pop(node_id)

    def total_cpus(self) -> int:
        return sum(n.cpus_total for n in self.nodes.values())

    def used_cpus(self) -> int:
        return sum(n.cpus_used for n in self.nodes.values())

    def free_cpus(self) -> int:
        return self.total_cpus() - self.used_cpus()
