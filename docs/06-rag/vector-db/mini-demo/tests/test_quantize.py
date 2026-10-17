import numpy as np
import pytest

from vector_db_mini.quantize import ProductQuantizer, ScalarQuantizer, _kmeans


@pytest.fixture
def data():
    rng = np.random.RandomState(42)
    return rng.rand(200, 16) * 4.0 - 1.0


class TestScalarQuantizer:
    def test_encode_decode_shape(self, data):
        sq = ScalarQuantizer(bits=8).fit(data)
        codes = sq.encode(data)
        assert codes.shape == (200, 16)
        recon = sq.decode(codes)
        assert recon.shape == data.shape

    def test_reconstruction_error_small(self, data):
        sq = ScalarQuantizer(bits=8).fit(data)
        recon = sq.decode(sq.encode(data))
        rel = np.linalg.norm(recon - data) / np.linalg.norm(data)
        assert rel < 0.02

    def test_codes_within_levels(self, data):
        sq = ScalarQuantizer(bits=8).fit(data)
        codes = sq.encode(data)
        assert codes.min() >= 0
        assert codes.max() <= sq.levels

    def test_deterministic(self, data):
        a = ScalarQuantizer(bits=8).fit(data).encode(data)
        b = ScalarQuantizer(bits=8).fit(data).encode(data)
        np.testing.assert_array_equal(a, b)

    def test_compression_ratio(self, data):
        sq4 = ScalarQuantizer(bits=4)
        sq16 = ScalarQuantizer(bits=16)
        assert sq4.compression_ratio(16) == 4 / 64
        assert sq16.compression_ratio(16) == 0.25

    def test_constant_dimension_no_crash(self):
        v = np.ones((10, 4))
        sq = ScalarQuantizer(bits=8).fit(v)
        recon = sq.decode(sq.encode(v))
        np.testing.assert_allclose(recon, 1.0, atol=1e-9)

    def test_bits_validation(self):
        with pytest.raises(ValueError):
            ScalarQuantizer(bits=0)
        with pytest.raises(ValueError):
            ScalarQuantizer(bits=17)


class TestProductQuantizer:
    def test_fit_encode_decode(self, data):
        pq = ProductQuantizer(m=4, k=8, seed=0).fit(data)
        codes = pq.encode(data)
        assert codes.shape == (200, 4)
        assert codes.min() >= 0 and codes.max() < 8
        recon = pq.decode(codes)
        assert recon.shape == data.shape

    def test_relative_error_reasonable(self, data):
        pq = ProductQuantizer(m=8, k=16, seed=0).fit(data)
        recon = pq.decode(pq.encode(data))
        rel = np.linalg.norm(recon - data) / np.linalg.norm(data)
        assert 0.0 < rel < 0.25

    def test_more_subspaces_reduce_error(self, data):
        errs = []
        for m in (2, 4, 8):
            pq = ProductQuantizer(m=m, k=16, seed=0).fit(data)
            recon = pq.decode(pq.encode(data))
            errs.append(np.linalg.norm(recon - data) / np.linalg.norm(data))
        assert errs[0] > errs[1] > errs[2]

    def test_adc_matches_decode_distance(self, data):
        pq = ProductQuantizer(m=4, k=8, seed=0).fit(data)
        codes = pq.encode(data)
        q = data[0]
        adc = pq.adc_distances(q, codes)
        recon = pq.decode(codes)
        direct_sq = np.sum((recon - q) ** 2, axis=1)
        np.testing.assert_allclose(adc, direct_sq, rtol=1e-9)

    def test_adc_argmin_selects_nearest_centroid(self, data):
        pq = ProductQuantizer(m=4, k=8, seed=0).fit(data)
        q = data[7]
        adc = pq.adc_distances(q, pq.encode(data))
        assert int(np.argmin(adc)) == 7  # exact for the training sample

    def test_deterministic_across_instances(self, data):
        a = ProductQuantizer(m=4, k=8, seed=0).fit(data).encode(data)
        b = ProductQuantizer(m=4, k=8, seed=0).fit(data).encode(data)
        np.testing.assert_array_equal(a, b)

    def test_m_must_divide_dim(self, data):
        with pytest.raises(ValueError):
            ProductQuantizer(m=5, k=8).fit(data)

    def test_compression_ratio(self, data):
        pq = ProductQuantizer(m=4, k=16).fit(data)
        # 4 subspaces * 4 bits = 16 bits vs 16 dims * 64 bits
        assert pq.compression_ratio() == pytest.approx(16 / (64 * 16))

    def test_encode_before_fit_raises(self, data):
        pq = ProductQuantizer(m=4, k=8)
        with pytest.raises(RuntimeError):
            pq.encode(data)


class TestKMeans:
    def test_assignments_in_range(self, data):
        centroids, assign = _kmeans(data, k=8, seed=1)
        assert centroids.shape == (8, 16)
        assert assign.shape == (200,)
        assert assign.min() >= 0 and assign.max() < 8

    def test_deterministic(self, data):
        c1, a1 = _kmeans(data, k=8, seed=1)
        c2, a2 = _kmeans(data, k=8, seed=1)
        np.testing.assert_allclose(c1, c2)
        np.testing.assert_array_equal(a1, a2)
