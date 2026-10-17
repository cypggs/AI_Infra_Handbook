"""Tests for SDC detection models."""
import numpy as np
import pytest

from training_reliability_mini import sdc


def test_deterministic_grad_reproducible():
    a = sdc.deterministic_grad(42, dim=256)
    b = sdc.deterministic_grad(42, dim=256)
    c = sdc.deterministic_grad(43, dim=256)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_inject_bit_flips_deterministic():
    vec = sdc.deterministic_grad(7, dim=64)
    a = sdc.inject_bit_flips(vec, 3, seed=1)
    b = sdc.inject_bit_flips(vec, 3, seed=1)
    c = sdc.inject_bit_flips(vec, 3, seed=2)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)
    assert sdc.hamming_distance(vec, a) >= 1


def test_hamming_distance_exact():
    vec = np.zeros(4, dtype=np.float64)
    one_bit = vec.copy()
    one_bit.view(np.uint64)[0] = np.uint64(1)  # single bit set
    assert sdc.hamming_distance(vec, one_bit) == 1
    assert sdc.hamming_distance(vec, vec) == 0


def test_hamming_distance_shape_check():
    with pytest.raises(ValueError):
        sdc.hamming_distance(np.zeros(4), np.zeros(5))


def test_dual_run_clean_no_mismatch():
    res = sdc.dual_run_compare(123, dim=512)
    assert res["mismatch"] is False
    assert res["bits_differing"] == 0


def test_dual_run_detects_corruption():
    res = sdc.dual_run_compare(123, dim=512, n_flips=2, inject_seed=9)
    assert res["mismatch"] is True
    assert res["bits_differing"] >= 1


def test_shard_fingerprints_locate_injected():
    rng = np.random.RandomState(0)
    shards = np.vstack([sdc.deterministic_grad(int(s), 128)
                        for s in rng.randint(0, 10**6, 16)])
    corrupted = shards.copy()
    corrupted[9] = sdc.inject_bit_flips(shards[9], 4, seed=5)
    np.testing.assert_array_equal(sdc.locate_corrupted_shards(shards, corrupted), [9])


def test_shard_fingerprints_clean_returns_minus_one():
    rng = np.random.RandomState(0)
    shards = np.vstack([sdc.deterministic_grad(int(s), 128)
                        for s in rng.randint(0, 10**6, 16)])
    assert sdc.locate_corrupted_shards(shards, shards.copy()).size == 0


def test_spike_indices_hits_injected_spike():
    losses = np.ones(200)
    losses[100] = 10.0  # 10x spike
    hits = sdc.spike_indices(losses, factor=5.0)
    assert list(hits) == [100]


def test_spike_indices_clean_curve_no_flags():
    losses = 2.5 * np.exp(-np.arange(500) / 400.0) + 0.1
    assert sdc.spike_indices(losses, factor=5.0).size == 0


def test_spike_indices_diverging_run_not_flagged_forever():
    # Genuinely diverging loss (growing 1%/step) must not fire every step:
    # the rolling median rises with it.
    losses = np.exp(np.arange(300) * 0.01)
    hits = sdc.spike_indices(losses, factor=5.0)
    assert hits.size <= 5


