"""End-to-end tests for the demo scenarios."""
from ray_mini.demo import (
    demo_ownership_and_reconstruction,
    demo_hybrid_scheduling,
    demo_autoscaler,
    demo_object_store_spilling,
)


def test_demo_ownership_and_reconstruction():
    result = demo_ownership_and_reconstruction()
    assert result.tasks_reconstructed >= 1


def test_demo_hybrid_scheduling():
    result = demo_hybrid_scheduling()
    assert len(result.scheduling_choices) == 7  # produce + 6 dependent tasks


def test_demo_autoscaler():
    result = demo_autoscaler()
    assert result.nodes_added >= 1


def test_demo_object_store_spilling():
    result = demo_object_store_spilling()
    # Spilling or eviction should occur because we exceed the threshold.
    assert result.objects_spilled + result.objects_evicted >= 1
