import numpy as np
import pytest

from feature_store_mini.skew import detect_skew, feature_distribution, psi


def test_distribution_basic():
    d = feature_distribution([1.0, 2.0, 3.0, 4.0])
    assert d["count"] == 4
    assert d["mean"] == pytest.approx(2.5)
    assert d["min"] == 1.0
    assert d["max"] == 4.0


def test_distribution_std():
    d = feature_distribution([2.0, 2.0, 2.0])
    assert d["std"] == pytest.approx(0.0)


def test_distribution_empty_rejected():
    with pytest.raises(ValueError):
        feature_distribution([])


def test_psi_identical_samples_is_zero():
    sample = list(range(100))
    assert psi(sample, sample, bins=10) == pytest.approx(0.0, abs=1e-9)


def test_psi_shifted_sample_is_elevated():
    expected = np.linspace(0, 1, 500).tolist()
    actual = (np.linspace(0, 1, 500) + 0.5).tolist()  # distribution shifted right
    assert psi(expected, actual, bins=10) > 0.25


def test_psi_empty_rejected():
    with pytest.raises(ValueError):
        psi([], [1.0])


def test_detect_skew_identical_pairs():
    report = detect_skew([(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)])
    assert not report["skewed"]
    assert report["compared"] == 3
    assert report["mismatched"] == 0
    assert report["max_abs_diff"] == 0.0


def test_detect_skew_window_bug():
    offline = [100.0, 200.0, 300.0]
    serving = [50.0, 100.0, 150.0]  # e.g. wrong aggregation window
    report = detect_skew(list(zip(offline, serving)), abs_tol=1e-9)
    assert report["skewed"]
    assert report["mismatched"] == 3
    assert report["max_abs_diff"] == pytest.approx(150.0)


def test_detect_skew_within_tolerance():
    report = detect_skew([(100.0, 100.1), (200.0, 200.2)], abs_tol=0.5)
    assert not report["skewed"]


def test_detect_skew_relative_tolerance():
    report = detect_skew([(100.0, 100.1), (200.0, 200.1)], abs_tol=0.0, rel_tol=1e-3)
    assert not report["skewed"]


def test_detect_skew_empty_rejected():
    with pytest.raises(ValueError):
        detect_skew([])


def test_detect_skew_examples_limited():
    pairs = [(float(i), float(i) + 1.0) for i in range(10)]
    report = detect_skew(pairs, abs_tol=1e-9)
    assert report["skewed"]
    assert len(report["examples"]) == 5
