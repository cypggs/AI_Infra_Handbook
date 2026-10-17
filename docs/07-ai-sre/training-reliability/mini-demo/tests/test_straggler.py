"""Tests for straggler detection and mitigation."""
import numpy as np
import pytest

from training_reliability_mini import straggler as st


def test_step_time_is_max():
    ranks = np.array([30.0, 31.0, 36.0, 29.5])
    assert st.step_time_s(ranks) == 36.0


def test_step_time_empty_raises():
    with pytest.raises(ValueError):
        st.step_time_s(np.array([]))


def test_outlier_scores_median_baseline():
    ranks = np.array([30.0, 30.0, 36.0])
    scores = st.outlier_scores(ranks)
    assert scores[2] == pytest.approx(36.0 / 30.0 - 1.0)
    assert np.allclose(scores[:2], 0.0)


def test_detect_stragglers_flags_slow_rank():
    ranks = np.full(64, 30.0)
    ranks[5] = 36.0  # 20% slower than median
    flagged = st.detect_stragglers(ranks, threshold=0.15)
    assert list(flagged) == [5]


def test_detect_stragglers_clean_ranks_no_flags():
    ranks = st.simulate_jittered_ranks(1024, 30.0, 0.5, seed=11)
    assert st.detect_stragglers(ranks, threshold=0.15).size == 0


def test_detect_stragglers_threshold_respected():
    ranks = np.full(64, 30.0)
    ranks[5] = 33.0  # 10% slower
    assert st.detect_stragglers(ranks, threshold=0.15).size == 0
    assert list(st.detect_stragglers(ranks, threshold=0.05)) == [5]


def test_mitigate_replace_recovers_step_time():
    ranks = np.full(64, 30.0)
    ranks[5] = 36.0
    fixed = st.mitigate(ranks, np.array([5]), replacement_time_s=30.0)
    assert fixed.shape == (64,)
    assert st.step_time_s(fixed) == pytest.approx(30.0)


def test_mitigate_evict_shrinks_world():
    ranks = np.full(64, 30.0)
    ranks[5] = 36.0
    fixed = st.mitigate(ranks, np.array([5]))
    assert fixed.shape == (63,)
    assert st.step_time_s(fixed) == pytest.approx(30.0)


def test_detection_report_metrics():
    rep = st.detection_report({1, 2}, {2, 3})
    assert rep["precision"] == pytest.approx(0.5)
    assert rep["recall"] == pytest.approx(0.5)
    perfect = st.detection_report({1}, {1})
    assert perfect == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    empty = st.detection_report(set(), set())
    assert empty["precision"] == 1.0 and empty["recall"] == 1.0


def test_simulate_jittered_ranks_deterministic():
    a = st.simulate_jittered_ranks(128, 30.0, 0.5, seed=11, slow_ranks={7: 1.2})
    b = st.simulate_jittered_ranks(128, 30.0, 0.5, seed=11, slow_ranks={7: 1.2})
    np.testing.assert_array_equal(a, b)
    assert a[7] == pytest.approx(36.0)
    assert a.shape == (128,)


def test_slow_rank_inflates_every_step():
    # Synchronous semantics: one 20%-slow rank inflates every step by 20%.
    clean = st.simulate_jittered_ranks(1024, 30.0, 0.0, seed=1)
    dirty = st.simulate_jittered_ranks(1024, 30.0, 0.0, seed=1, slow_ranks={7: 1.2})
    assert st.step_time_s(clean) == pytest.approx(30.0)
    assert st.step_time_s(dirty) == pytest.approx(36.0)
