"""Tests for the autoscaler."""
from ray_mini.autoscaler import Autoscaler
from ray_mini.model import Config
from ray_mini.runtime import MiniRay


def test_scale_up_on_pending_demand():
    config = Config(num_nodes=1, cpus_per_node=2, autoscaler_max_nodes=4)
    ray = MiniRay(config)
    autoscaler = Autoscaler(1, 4, idle_timeout_ticks=2)

    for _ in range(6):
        ray.submit("t", cost=1, num_cpus=1)

    while ray._pending or ray._running:
        ray._step()
        autoscaler.step(ray)

    assert ray.result().nodes_added >= 1
    assert ray.result().nodes_added >= 1


def test_scale_down_idle_nodes():
    config = Config(
        num_nodes=2,
        cpus_per_node=2,
        autoscaler_min_nodes=1,
        autoscaler_max_nodes=4,
        idle_timeout_ticks=1,
    )
    ray = MiniRay(config)
    autoscaler = Autoscaler(1, 4, idle_timeout_ticks=1)

    # Run a task so nodes exist, then let everything finish and idle out.
    ray.submit("t", cost=1).id
    ray.run_until_done()

    # Tick autoscaler enough times to idle-timeout the worker.
    for _ in range(5):
        autoscaler.step(ray)

    assert len(ray.cluster.nodes) == 1
    assert ray.result().nodes_removed == 1


def test_never_remove_head_node():
    config = Config(num_nodes=1, cpus_per_node=2)
    ray = MiniRay(config)
    autoscaler = Autoscaler(1, 1, idle_timeout_ticks=0)
    autoscaler.step(ray)
    assert len(ray.cluster.nodes) == 1
