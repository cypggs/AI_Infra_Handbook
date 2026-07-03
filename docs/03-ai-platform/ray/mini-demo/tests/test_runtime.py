"""Tests for the MiniRay runtime."""
import pytest

from ray_mini.model import Config, OwnerDiedError, ObjectLostError
from ray_mini.runtime import MiniRay


def test_put_and_get():
    ray = MiniRay(Config(num_nodes=1, cpus_per_node=2))
    ref = ray.put(size=5)
    assert ray.get(ref) == 5


def test_submit_and_get():
    ray = MiniRay(Config(num_nodes=2, cpus_per_node=2))
    ref = ray.submit("inc", cost=1, result_size=3)
    assert ray.get(ref) == 3
    assert ray.result().tasks_executed == 1


def test_task_dependency():
    ray = MiniRay(Config(num_nodes=2, cpus_per_node=2))
    a = ray.submit("a", cost=1, result_size=2)
    b = ray.submit("b", arg_refs=(a,), cost=1, result_size=4)
    assert ray.get(b) == 4


def test_lineage_reconstruction_after_worker_failure():
    ray = MiniRay(Config(num_nodes=3, cpus_per_node=2, object_store_capacity=500))
    # Make a large enough to be reconstructable.
    a = ray.submit("a", cost=1, result_size=200_000)
    b = ray.submit("b", arg_refs=(a,), cost=1, result_size=200_000)
    ray.run_until_done()

    location = ray._arg_locations[a.id]
    ray.fail_node(location)

    # b is still owned by the head node; a can be reconstructed.
    assert ray.get(b) == 200_000
    assert ray.result().tasks_reconstructed >= 1


def test_ray_put_not_reconstructable_on_owner_failure():
    ray = MiniRay(Config(num_nodes=2, cpus_per_node=2))
    ref = ray.put(size=5)
    ray.fail_node(ray._driver_node)
    with pytest.raises(OwnerDiedError):
        ray.get(ref)


def test_actor_state():
    ray = MiniRay(Config(num_nodes=2, cpus_per_node=2))
    ray.actor(1, node_id=0)
    ray.actor_call(1, delta=5)
    ray.actor_call(1, delta=3)
    assert ray._actors[1]["state"] == 8


def test_head_failure_blocks_new_submissions():
    ray = MiniRay(Config(num_nodes=2, cpus_per_node=2))
    ray.fail_node(ray._driver_node)
    with pytest.raises(OwnerDiedError):
        ray.put(1)
    with pytest.raises(OwnerDiedError):
        ray.submit("x")
