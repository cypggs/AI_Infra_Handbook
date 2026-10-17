import numpy as np
import pytest

from vector_db_mini.metric import (
    METRICS,
    cosine_distance,
    inner_product,
    l2_distance,
    normalize,
    pairwise_distance,
    top_k,
)


def test_l2_known_values():
    a = np.array([[0.0, 0.0]])
    b = np.array([[3.0, 4.0]])
    assert l2_distance(a, b)[0, 0] == pytest.approx(5.0)


def test_l2_is_zero_for_identical_rows():
    x = np.array([[1.0, 2.0, 3.0]])
    assert l2_distance(x, x)[0, 0] == pytest.approx(0.0)


def test_ip_negative_as_distance():
    a = np.array([[1.0, 0.0]])
    b = np.array([[2.0, 0.0], [-1.0, 0.0]])
    d = -inner_product(a, b)  # our ip distance convention
    assert d[0, 0] == pytest.approx(-2.0)
    assert d[0, 1] == pytest.approx(1.0)
    assert d[0, 0] < d[0, 1]  # larger inner product == smaller distance


def test_cosine_identical_and_orthogonal():
    x = np.array([[1.0, 0.0]])
    same = np.array([[5.0, 0.0]])
    orth = np.array([[0.0, 7.0]])
    assert cosine_distance(x, same)[0, 0] == pytest.approx(0.0, abs=1e-9)
    assert cosine_distance(x, orth)[0, 0] == pytest.approx(1.0)


def test_cosine_equals_half_l2_on_unit_vectors():
    rng = np.random.RandomState(7)
    a = normalize(rng.randn(4, 8))
    b = normalize(rng.randn(4, 8))
    cos_d = cosine_distance(a, b)
    l2_d = l2_distance(a, b)
    np.testing.assert_allclose(cos_d, 0.5 * l2_d ** 2, rtol=1e-9)


def test_normalize_unit_norm_and_zero_rows():
    rng = np.random.RandomState(3)
    v = rng.randn(5, 6)
    n = normalize(v)
    norms = np.linalg.norm(n, axis=1)
    np.testing.assert_allclose(norms, 1.0, rtol=1e-9)
    zero = normalize(np.zeros((2, 4)))
    assert np.all(zero == 0.0)


def test_pairwise_distance_dispatch_and_shape():
    a = np.zeros((3, 4))
    b = np.ones((5, 4))
    for m in METRICS:
        d = pairwise_distance(a, b, m)
        assert d.shape == (3, 5)
    with pytest.raises(ValueError):
        pairwise_distance(a, b, "manhattan")


def test_pairwise_accepts_1d_query():
    q = np.zeros(4)
    b = np.ones((5, 4))
    d = pairwise_distance(q, b, "l2")
    assert d.shape == (1, 5)


def test_top_k_stable_and_bounded():
    d = np.array([0.3, 0.1, 0.1, 0.2])
    idx = top_k(d, 3)
    assert list(idx) == [1, 2, 3]  # ties keep original order
    assert len(top_k(d, 100)) == 4  # k larger than n is clamped
