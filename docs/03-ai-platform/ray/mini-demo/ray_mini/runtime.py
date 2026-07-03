"""Mini Ray runtime: submit / get / put / actor / failure / reconstruction."""
from __future__ import annotations

import random
from typing import Optional, Union

from .cluster import Cluster
from .model import Config, ObjectRef, OwnerDiedError, ObjectLostError, SimResult, Task, INLINE_OBJECT_SIZE_BYTES
from .scheduler import HybridScheduler


class MiniRay:
    """Deterministic synchronous simulator of Ray Core observable behavior."""

    def __init__(self, config: Optional[Config] = None, seed: Optional[int] = None):
        self.config = config or Config()
        self.cluster = Cluster(self.config)
        self.scheduler = HybridScheduler(self.config.spread_threshold, self.config.top_k_fraction)

        self._rng = random.Random(seed if seed is not None else self.config.seed)
        self._next_ref_id = 0
        self._next_task_id = 0

        # Execution state
        self._pending: list[Task] = []  # waiting to be scheduled
        self._running: dict[int, tuple[Task, int, int]] = {}  # task_id -> (task, node_id, remaining_cost)
        self._refs: dict[int, ObjectRef] = {}
        self._arg_locations: dict[int, int] = {}  # ref_id -> node_id of primary copy
        self._completed: dict[int, int] = {}  # task_id -> result_ref_id
        self._actors: dict[int, dict] = {}  # actor_id -> {node_id, state, ...}
        self._task_result_ref: dict[int, int] = {}  # task_id -> result ref id

        self._tick = 0
        self._result = SimResult("simulation")
        self._driver_node = 0
        self._head_alive = True
        self._finished = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def put(self, size: int = 1) -> ObjectRef:
        """ray.put: store a primary copy on the driver's node. Not reconstructable."""
        self._ensure_head_alive()
        ref = self._new_ref(size, generating_task=None, small_inline=False)
        # A ray.put object's primary copy lives on the owner (driver) node.
        self.cluster.nodes[self._driver_node].store.put_primary(ref)
        self._arg_locations[ref.id] = self._driver_node
        return ref

    def submit(
        self,
        fn_name: str,
        arg_refs: tuple = (),
        cost: int = 1,
        result_size: int = 1,
        num_cpus: int = 1,
    ) -> ObjectRef:
        """fn.remote(...): create a task, schedule it, return an ObjectRef future."""
        self._ensure_head_alive()
        task = Task(
            id=self._next_task_id,
            fn_name=fn_name,
            arg_refs=arg_refs,
            cost=max(1, cost),
            result_size=result_size,
            num_cpus=num_cpus,
        )
        self._next_task_id += 1

        # The ObjectRef is owned by the submitting worker (driver).
        ref = self._new_ref(
            result_size,
            generating_task=task,
            small_inline=(result_size <= INLINE_OBJECT_SIZE_BYTES),
        )
        self._task_result_ref[task.id] = ref.id
        # Local ref held by driver until ray.get consumes it.
        self.cluster.nodes[self._driver_node].store.add_ref(ref.id)

        self._pending.append(task)
        return ref

    def get(self, ref: Union[int, ObjectRef]) -> int:
        """ray.get: block until the object is available, then return its size.

        Raises OwnerDiedError if the owner died and the object is not
        reconstructable; raises ObjectLostError if the object cannot be
        resolved anywhere.
        """
        self._ensure_head_alive()
        ref_id = ref if isinstance(ref, int) else ref.id
        if ref_id not in self._refs:
            raise ObjectLostError(f"Unknown ObjectRef {ref_id}")
        obj = self._refs[ref_id]

        # Owner died -> only reconstructable objects can be rebuilt.
        if not self._head_alive:
            if not obj.is_reconstructable:
                self._result.owner_died_errors += 1
                raise OwnerDiedError(f"Owner of ObjectRef {ref_id} died; object is not reconstructable")
            self._reconstruct(obj)

        # Run simulation forward until the object is local or reconstructable.
        while not self._is_resolved_locally(ref_id):
            if self._is_available_somewhere(ref_id):
                # Object exists on a worker; pull an evictable copy to the driver.
                self.cluster.nodes[self._driver_node].store.add_evictable_copy(obj)
                break
            if not self._step():
                # No forward progress possible; try reconstruction as last resort.
                if obj.is_reconstructable:
                    self._reconstruct(obj)
                    continue
                raise ObjectLostError(f"ObjectRef {ref_id} cannot be resolved")

        # "Deserialize" (touch local copy).
        self.cluster.nodes[self._driver_node].store.get(ref_id)
        return obj.size

    def actor(self, actor_id: int, node_id: Optional[int] = None) -> int:
        """Create a stateful actor on a node (simplified: no methods in this demo)."""
        self._ensure_head_alive()
        if node_id is None:
            node_id = self.scheduler.choose_node(self.cluster, Task(id=-1, fn_name="actor", num_cpus=1), {})
        if node_id is None:
            raise RuntimeError("No node can host actor")
        self.cluster.nodes[node_id].allocate_cpu(1)
        self._actors[actor_id] = {"node_id": node_id, "state": 0}
        return actor_id

    def actor_call(self, actor_id: int, delta: int = 1) -> None:
        """Simulate a stateful actor method call."""
        self._ensure_head_alive()
        actor = self._actors.get(actor_id)
        if actor is None:
            raise RuntimeError(f"Actor {actor_id} not found")
        if actor["node_id"] not in self.cluster.nodes:
            raise OwnerDiedError(f"Actor {actor_id} died with its node")
        actor["state"] += delta

    def fail_node(self, node_id: int) -> dict:
        """Simulate a node failure; return what was lost from its object store."""
        if node_id not in self.cluster.nodes:
            return {}
        lost = self.cluster.nodes[node_id].store.lose_all()
        # Release CPU allocations on this node.
        for task_id, (task, tnode, _) in list(self._running.items()):
            if tnode == node_id:
                del self._running[task_id]
                self._pending.append(task)  # will be rescheduled
        node = self.cluster.remove_node(node_id)
        self._result.tasks_reconstructed += 0  # reconstruction happens lazily on get
        self._result.nodes_removed += 1
        if node_id == self._driver_node:
            self._head_alive = False
        return lost

    def scale_up(self, node_id: int) -> Node:
        """Autoscaler hook: add a node to the cluster."""
        node = self.cluster.add_node(node_id)
        self._result.nodes_added += 1
        return node

    def tick(self) -> bool:
        """Advance one simulation tick. Returns True if anything happened."""
        return self._step()

    def run_until_done(self) -> SimResult:
        """Run all pending and running tasks to completion."""
        while self._step():
            pass
        return self._result

    def result(self) -> SimResult:
        # Aggregate object-store stats from all nodes.
        self._result.objects_spilled = sum(n.store.spill_count for n in self.cluster.nodes.values())
        self._result.objects_evicted = sum(n.store.evict_count for n in self.cluster.nodes.values())
        return self._result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _new_ref(
        self,
        size: int,
        generating_task: Optional[Task] = None,
        small_inline: bool = False,
    ) -> ObjectRef:
        ref = ObjectRef(
            id=self._next_ref_id,
            size=size,
            owner_node=self._driver_node,
            generating_task=generating_task,
            small_inline=small_inline,
        )
        self._next_ref_id += 1
        self._refs[ref.id] = ref
        return ref

    def _ensure_head_alive(self) -> None:
        if not self._head_alive:
            raise OwnerDiedError("Driver/head node has failed")

    def _args_ready(self, task: Task) -> bool:
        """A task's arguments are ready if they are put objects or completed tasks."""
        for arg in task.arg_refs:
            if arg.generating_task is None:
                continue  # ray.put object, always ready
            if arg.generating_task.id not in self._completed:
                return False
        return True

    def _is_resolved_locally(self, ref_id: int) -> bool:
        return self.cluster.nodes[self._driver_node].store.has(ref_id)

    def _is_available_somewhere(self, ref_id: int) -> bool:
        return any(n.store.has(ref_id) for n in self.cluster.nodes.values())

    def _step(self) -> bool:
        """One tick: schedule pending tasks, decrement running tasks, finish any."""
        progressed = False

        # Try to schedule pending tasks (driver node does not execute tasks).
        still_pending: list[Task] = []
        for task in self._pending:
            if not self._args_ready(task):
                still_pending.append(task)
                continue
            node_id = self.scheduler.choose_node(
                self.cluster, task, self._arg_locations, exclude_nodes={self._driver_node}
            )
            if node_id is None:
                still_pending.append(task)
                continue
            node = self.cluster.nodes[node_id]
            node.allocate_cpu(task.num_cpus)
            self._running[task.id] = (task, node_id, task.cost)
            self._result.scheduling_choices.append((task.id, node_id))
            progressed = True
        self._pending = still_pending

        # Decrement running tasks.
        finishing: list[tuple[Task, int]] = []
        still_running: dict[int, tuple[Task, int, int]] = {}
        for task_id, (task, node_id, remaining) in self._running.items():
            # Ensure inputs are local before the *first* tick of execution.
            if remaining == task.cost:
                if not self._fetch_args(node_id, task):
                    # Args not yet available (reconstruction in flight); try next tick.
                    still_running[task_id] = (task, node_id, remaining)
                    continue
            new_remaining = remaining - 1
            if new_remaining <= 0:
                finishing.append((task, node_id))
            else:
                still_running[task_id] = (task, node_id, new_remaining)
            progressed = True
        self._running = still_running

        # Finish tasks.
        for task, node_id in finishing:
            self._finish_task(task, node_id)
            progressed = True

        self._tick += 1
        return progressed

    def _fetch_args(self, node_id: int, task: Task) -> bool:
        """Ensure argument objects are present on the executing node.

        Returns True if all args are present, False if reconstruction was
        triggered and the task must wait for the next tick.
        """
        node = self.cluster.nodes[node_id]
        wait = False
        for arg in task.arg_refs:
            if node.store.has(arg.id):
                continue
            # If the primary copy is lost, try lineage reconstruction.
            primary_node = self._arg_locations.get(arg.id)
            if primary_node not in self.cluster.nodes:
                if arg.is_reconstructable:
                    self._reconstruct(arg)
                    wait = True
                    continue
                raise ObjectLostError(f"Argument ObjectRef {arg.id} lost and not reconstructable")
            node.store.add_evictable_copy(arg)
        return not wait

    def _finish_task(self, task: Task, node_id: int) -> None:
        """Task completed: produce its result object on the executing node."""
        node = self.cluster.nodes[node_id]
        node.release_cpu(task.num_cpus)

        ref_id = self._task_result_ref.get(task.id)
        if ref_id is None:
            # Should not happen; create a fallback.
            ref = self._new_ref(task.result_size, generating_task=task)
            self._task_result_ref[task.id] = ref.id
            ref_id = ref.id
        ref = self._refs[ref_id]
        self._arg_locations[ref.id] = node_id
        node.store.put_primary(ref)
        self._completed[task.id] = ref.id
        self._result.tasks_executed += 1

    def _reconstruct(self, obj: ObjectRef) -> None:
        """Lineage reconstruction: re-submit the generating task if possible."""
        task = obj.generating_task
        if task is None:
            raise ObjectLostError(f"ObjectRef {obj.id} has no lineage")
        # Do not double-schedule.
        if task.id in self._running or task in self._pending:
            return
        # Allow re-execution even if the task previously completed; its primary
        # copy may have been lost due to node failure.
        self._completed.pop(task.id, None)
        self._pending.append(task)
        self._result.tasks_reconstructed += 1
