"""Tests for the hybrid scheduler."""
from ray_mini.cluster import Cluster
from ray_mini.model import Config, Task, ObjectRef
from ray_mini.scheduler import HybridScheduler


def test_locality_preference():
    config = Config(num_nodes=3, cpus_per_node=2)
    cluster = Cluster(config)
    scheduler = HybridScheduler(spread_threshold=1.0, top_k_fraction=1.0)

    # Put a primary copy of ref 1 on node 2.
    ref = ObjectRef(id=1, size=1, owner_node=0)
    cluster.nodes[2].store.put_primary(ref)
    arg_locations = {1: 2}

    task = Task(id=0, fn_name="f", arg_refs=(ref,), num_cpus=1)
    chosen = scheduler.choose_node(cluster, task, arg_locations)
    assert chosen == 2


def test_spread_when_over_threshold():
    config = Config(num_nodes=3, cpus_per_node=2)
    cluster = Cluster(config)
    scheduler = HybridScheduler(spread_threshold=0.3, top_k_fraction=1.0)

    # Make node 0 heavily utilized.
    cluster.nodes[0].allocate_cpu(1)
    cluster.nodes[1].allocate_cpu(0)

    task = Task(id=0, fn_name="f", num_cpus=1)
    chosen = scheduler.choose_node(cluster, task, {})
    # utilization(0)=0.5 > 0.3, so it should spread to least utilized top-k node.
    assert chosen == 1


def test_no_node_fits():
    config = Config(num_nodes=2, cpus_per_node=1)
    cluster = Cluster(config)
    cluster.nodes[0].allocate_cpu(1)
    cluster.nodes[1].allocate_cpu(1)
    scheduler = HybridScheduler(spread_threshold=1.0, top_k_fraction=1.0)

    task = Task(id=0, fn_name="f", num_cpus=1)
    assert scheduler.choose_node(cluster, task, {}) is None
