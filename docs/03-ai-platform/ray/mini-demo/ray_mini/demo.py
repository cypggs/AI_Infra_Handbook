"""Deterministic demo scenarios for the mini Ray simulator."""
from __future__ import annotations

from .autoscaler import Autoscaler
from .model import Config, SimResult
from .runtime import MiniRay


def _banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def demo_ownership_and_reconstruction() -> SimResult:
    """Show task-generated objects reconstruct after worker failure, but ray.put objects do not."""
    _banner("Demo 1: Ownership + lineage reconstruction")
    config = Config(num_nodes=3, cpus_per_node=2, object_store_capacity=50)
    ray = MiniRay(config)

    # A dataset object placed by ray.put lives on the driver/owner node.
    dataset = ray.put(size=10)
    print(f"ray.put dataset -> ObjectRef({dataset.id}), owned by node {dataset.owner_node}")

    # A task reads the dataset and produces an intermediate result.
    # Use a size above the inline threshold so the object is reconstructable.
    intermediate = ray.submit("preprocess", arg_refs=(dataset,), cost=2, result_size=200_000)
    print(f"submit preprocess(dataset) -> ObjectRef({intermediate.id}) (task-generated, reconstructable)")

    # Another task consumes the intermediate. Result size is deliberately large
    # enough to NOT be a small inline object, so it is reconstructable too.
    final = ray.submit("train", arg_refs=(intermediate,), cost=3, result_size=200_000)
    print(f"submit train(intermediate) -> ObjectRef({final.id})")

    # Let preprocessing finish so the intermediate object lands on a worker.
    ray.run_until_done()
    print(f"tasks executed before failure: {ray.result().tasks_executed}")

    # Simulate failure of the worker that holds the intermediate primary copy.
    intermediate_location = ray._arg_locations[intermediate.id]
    print(f"failing worker node {intermediate_location} which holds intermediate primary copy")
    ray.fail_node(intermediate_location)

    # Now resolve final. This triggers lineage reconstruction of intermediate.
    try:
        ray.get(final)
        print(f"final object resolved after reconstruction")
    except Exception as exc:
        print(f"ERROR: {exc}")

    result = ray.run_until_done()
    print(f"tasks reconstructed: {result.tasks_reconstructed}")
    return result


def demo_hybrid_scheduling() -> SimResult:
    """Show locality preference, top-k group, and spread-threshold switching."""
    _banner("Demo 2: Hybrid scheduling (locality vs spread)")
    # Use top_k_fraction=1.0 so all workers are in the candidate group.
    config = Config(num_nodes=4, cpus_per_node=2, spread_threshold=0.5, top_k_fraction=1.0)
    ray = MiniRay(config)

    # Produce an object on a worker (not the driver) so dependent tasks have
    # a real locality preference.
    a = ray.submit("produce", cost=1, result_size=200_000)
    ray.run_until_done()
    location = ray._arg_locations[a.id]
    print(f"object `a` produced on worker node {location}")

    # Submit many tasks that read `a`. They should pack onto the worker that
    # holds `a` until its CPU utilization crosses the spread threshold.
    refs = [ray.submit(f"task_{i}", arg_refs=(a,), cost=1, result_size=1) for i in range(6)]
    ray.run_until_done()

    print("scheduling choices (task_id -> node_id):")
    for task_id, node_id in ray.result().scheduling_choices:
        marker = "*" if node_id == location else " "
        print(f"  task {task_id:3d} -> node {node_id} {marker}")
    return ray.result()


def demo_autoscaler() -> SimResult:
    """Show scale-up when pending demand exceeds capacity and scale-down on idle."""
    _banner("Demo 3: Autoscaler")
    config = Config(
        num_nodes=1,
        cpus_per_node=2,
        autoscaler_min_nodes=1,
        autoscaler_max_nodes=4,
        idle_timeout_ticks=2,
    )
    ray = MiniRay(config)
    autoscaler = Autoscaler(
        config.autoscaler_min_nodes,
        config.autoscaler_max_nodes,
        config.idle_timeout_ticks,
    )

    # More CPUs required than the initial single node can provide.
    for i in range(8):
        ray.submit(f"big_task_{i}", cost=2, num_cpus=1)

    print(f"initial nodes: {len(ray.cluster.nodes)}")
    while ray._pending or ray._running:
        ray._step()
        autoscaler.step(ray)
    print(f"final nodes: {len(ray.cluster.nodes)}")
    print(f"nodes added: {ray.result().nodes_added}, nodes removed: {ray.result().nodes_removed}")
    return ray.result()


def demo_object_store_spilling() -> SimResult:
    """Show eager spilling when evictable objects exceed the threshold."""
    _banner("Demo 4: Object-store spilling")
    config = Config(num_nodes=2, cpus_per_node=2, object_store_capacity=20, object_spilling_threshold=0.8)
    ray = MiniRay(config)

    # Produce task-generated objects on worker nodes; then pull them to the
    # driver as evictable copies. 4 objects × 6 units = 24 > 20 × 0.8 threshold.
    refs = [ray.submit(f"big_task_{i}", cost=1, result_size=6) for i in range(4)]
    ray.run_until_done()
    for ref in refs:
        ray.get(ref)

    result = ray.result()
    print(f"objects spilled: {result.objects_spilled}, objects evicted: {result.objects_evicted}")
    return result


def main() -> None:
    demo_ownership_and_reconstruction()
    demo_hybrid_scheduling()
    demo_autoscaler()
    demo_object_store_spilling()
    print("\nAll Ray mini-demo scenarios completed.")


if __name__ == "__main__":
    main()
