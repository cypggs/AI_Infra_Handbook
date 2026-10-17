"""Tests for the availability / MTBF-MTTR model."""
import numpy as np
import pytest

from training_reliability_mini import availability as av


def test_job_mtbf_scales_linearly():
    assert av.job_mtbf_hours(1024, 8089.6) == pytest.approx(7.9)


def test_job_mtbf_research_calibration():
    # Kokolis HPCA'25 anchor: 1,024-GPU job MTTF = 7.9 h.
    assert av.job_mtbf_hours(1024, av.NODE_MTBF_RESEARCH_CLUSTER_H) == pytest.approx(7.9)


def test_job_mtbf_llama3_implied_node_mtbf():
    # 466 interruptions / 54 days on 16,384 GPUs -> ~5.05 years per node.
    assert av.NODE_MTBF_LLAMA3_H == pytest.approx(45562.53, rel=1e-3)
    assert av.LLAMA3_INTERRUPTION_INTERVAL_H == pytest.approx(2.78, abs=0.01)


def test_job_mtbf_invalid():
    with pytest.raises(ValueError):
        av.job_mtbf_hours(0, 100.0)
    with pytest.raises(ValueError):
        av.job_mtbf_hours(10, -1.0)


def test_expected_interruptions_matches_mtbf():
    assert av.expected_interruptions(7.9, 1024, 8089.6) == pytest.approx(1.0)


def test_availability_bounds():
    assert av.availability(10.0, 1.0) == pytest.approx(10.0 / 11.0)
    assert av.availability(10.0, 0.0) == 1.0
    assert 0.0 < av.availability(1.0, 1000.0) < 1.0


def test_availability_invalid():
    with pytest.raises(ValueError):
        av.availability(0.0, 1.0)
    with pytest.raises(ValueError):
        av.availability(1.0, -1.0)


def test_ettr_simple_with_rollback():
    ettr = av.ettr_simple(7.9, 0.2, 0.1)
    assert ettr == pytest.approx(7.9 / 8.2)
    assert ettr < av.ettr_simple(7.9, 0.2, 0.0)


def test_scale_table_structure():
    rows = av.scale_table(8089.6, scales=(128, 1024))
    assert [r["nodes"] for r in rows] == [128, 1024]
    for r in rows:
        assert r["job_mtbf_h"] > 0
        assert 0.0 < r["avail_cold"] < 1.0
        assert r["avail_hot"] > r["avail_cold"]


def test_scale_table_availability_degrades_with_scale():
    rows = av.scale_table(8089.6)
    colds = [r["avail_cold"] for r in rows]
    assert colds == sorted(colds, reverse=True)


def test_simulate_interruption_times_deterministic():
    a = av.simulate_interruption_times(168.0, 1024, 8089.6, seed=3)
    b = av.simulate_interruption_times(168.0, 1024, 8089.6, seed=3)
    c = av.simulate_interruption_times(168.0, 1024, 8089.6, seed=4)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_simulate_interruption_times_rate():
    # Over many seeds the empirical rate approximates 1/MTBF (loose bound).
    counts = [len(av.simulate_interruption_times(168.0, 1024, 8089.6, seed=s))
              for s in range(50)]
    assert 5.0 < float(np.mean(counts)) < 35.0
