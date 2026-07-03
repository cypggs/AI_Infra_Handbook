"""Data structures for the mini Ray simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Mirror of Ray's max_direct_call_object_size (src/ray/common/ray_config_def.h):
# objects <= this live in the owner's in-process store, are returned inline,
# and are NOT reconstructable (they die with the owner).
INLINE_OBJECT_SIZE_BYTES = 100 * 1024  # 100 KiB


@dataclass(frozen=True)
class Config:
    """Cluster + runtime configuration."""

    # Cluster shape
    num_nodes: int = 4
    cpus_per_node: int = 8

    # Object store (Plasma). Capacity is in abstract "object units" to keep the
    # demo independent of real byte sizes; one unit == one object of size 1.
    object_store_capacity: int = 100
    object_spilling_threshold: float = 0.8  # eager spill at 80% (whitepaper)
    executing_task_arg_cap: float = 0.7     # in-flight args <= 70% of store

    # Scheduling (hybrid default policy)
    spread_threshold: float = 0.5   # RAY_scheduler_spread_threshold
    top_k_fraction: float = 0.2     # consider top 20% of nodes

    # Autoscaler
    autoscaler_min_nodes: int = 1
    autoscaler_max_nodes: int = 8
    idle_timeout_ticks: int = 3

    # Failure model
    seed: int = 7


@dataclass
class ObjectRef:
    """A future / reference to an object.

    Mirrors Ray's ObjectRef semantics:
      - ``owner_node`` is the node where the object's owner lives; if that node
        fails, the ref is gone (OwnerDiedError) unless the object is large and
        task-generated (then lineage reconstruction may re-create it elsewhere).
      - ``generating_task`` is the Task that produced this object (None for
        ray.put objects, which are NOT reconstructable).
      - ``small_inline`` marks objects <= INLINE_OBJECT_SIZE_BYTES that live in
        the owner's in-process store and are never spilled / never rebuilt.
    """

    id: int
    size: int
    owner_node: int
    generating_task: Optional["Task"] = None
    small_inline: bool = False

    @property
    def is_reconstructable(self) -> bool:
        """Rebuildable iff task-generated, not small-inline, and not ray.put."""
        return (
            self.generating_task is not None
            and not self.small_inline
        )


@dataclass
class Task:
    """A unit of work submitted via fn.remote(...)."""

    id: int
    fn_name: str
    arg_refs: tuple = ()        # ObjectRefs the task depends on
    cost: int = 1               # abstract compute cost
    result_size: int = 1        # size of the produced object
    num_cpus: int = 1


@dataclass
class SimResult:
    """Aggregated result of a simulation/scenario run."""

    label: str
    tasks_executed: int = 0
    tasks_reconstructed: int = 0          # lineage re-executions
    objects_spilled: int = 0
    objects_evicted: int = 0
    owner_died_errors: int = 0            # ray.put / small-inline losses
    nodes_added: int = 0
    nodes_removed: int = 0
    scheduling_choices: list = field(default_factory=list)  # (task_id, node_id)


class OwnerDiedError(RuntimeError):
    """Raised when ray.get hits an object whose owner node has died.

    Mirrors Ray's OwnerDiedError: ownership cannot be transferred, so a
    ray.put object (or a small inline object) is gone for good.
    """


class ObjectLostError(RuntimeError):
    """Raised when an object cannot be resolved and is not reconstructable."""
