"""Simplified Ray autoscaler: demand-based scale up, idle-timeout scale down."""
from __future__ import annotations

from .cluster import Cluster
from .runtime import MiniRay


class Autoscaler:
    """A teaching autoscaler mirroring Ray's node provider semantics.

    - Scale up when pending tasks cannot fit on current free CPUs and the
      cluster is below max_nodes.
    - Scale down nodes that have been idle (no running tasks, no primary
      objects) for more than idle_timeout_ticks.
    """

    def __init__(
        self,
        min_nodes: int,
        max_nodes: int,
        idle_timeout_ticks: int,
    ):
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.idle_timeout_ticks = idle_timeout_ticks
        self._idle_ticks: dict[int, int] = {}

    def step(self, ray: MiniRay) -> None:
        """Run one autoscaler decision tick."""
        cluster = ray.cluster
        self._scale_up(ray, cluster)
        self._scale_down(ray, cluster)

    def _scale_up(self, ray: MiniRay, cluster: Cluster) -> None:
        pending_cpus = sum(t.num_cpus for t in ray._pending)
        # Driver/head node does not execute tasks, so exclude it from capacity.
        executable_free = sum(
            n.cpus_free for n in cluster.nodes.values() if n.id != ray._driver_node
        )
        needed = max(0, pending_cpus - executable_free)

        while needed > 0 and len(cluster.nodes) < self.max_nodes:
            new_id = self._next_node_id(cluster)
            ray.scale_up(new_id)
            needed -= ray.config.cpus_per_node

    def _scale_down(self, ray: MiniRay, cluster: Cluster) -> None:
        # Never scale down while there is unscheduled demand on worker nodes.
        pending_demand = sum(t.num_cpus for t in ray._pending)
        executable_free = sum(
            n.cpus_free for n in cluster.nodes.values() if n.id != ray._driver_node
        )
        if pending_demand > executable_free:
            return

        for node_id, node in list(cluster.nodes.items()):
            if node_id == ray._driver_node:
                continue  # Never remove the head node.
            if node.cpus_used > 0:
                self._idle_ticks[node_id] = 0
                continue

            self._idle_ticks[node_id] = self._idle_ticks.get(node_id, 0) + 1
            if (
                self._idle_ticks[node_id] >= self.idle_timeout_ticks
                and len(cluster.nodes) > self.min_nodes
            ):
                ray.fail_node(node_id)
                self._idle_ticks.pop(node_id, None)

    @staticmethod
    def _next_node_id(cluster: Cluster) -> int:
        return max(cluster.nodes.keys(), default=-1) + 1
