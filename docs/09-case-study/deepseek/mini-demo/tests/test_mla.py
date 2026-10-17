"""mla.py 的测试：KV 压缩比、低秩重建、DSA 打分与选择。"""
import numpy as np
import pytest

from deepseek_case_mini.mla import (
    MlaConfig,
    compress_kv,
    kv_cache_bytes_per_token,
    kv_compression_ratio,
    kv_elements_mha,
    kv_elements_mla,
    latent_reconstruction_error,
    lightning_index_scores,
    make_mla_weights,
    reconstruct_heads,
    select_top_k,
    sparse_attention_flops_ratio,
    v3_reference_config,
)


class TestCacheAccounting:
    def test_mha_formula(self):
        cfg = MlaConfig(n_heads=16, d_head=32)
        assert kv_elements_mha(cfg) == 2 * 16 * 32

    def test_mla_formula(self):
        cfg = MlaConfig(n_latent=32, n_rope=8)
        assert kv_elements_mla(cfg) == 40

    def test_v3_compression_ratio(self):
        """V3 真实维度：2×128×128 / (512+64) = 32768/576 ≈ 56.9×。"""
        cfg = v3_reference_config()
        assert kv_elements_mha(cfg) == 32768
        assert kv_elements_mla(cfg) == 576
        assert kv_compression_ratio(cfg) == pytest.approx(32768 / 576, rel=1e-9)
        assert 56.0 < kv_compression_ratio(cfg) < 57.0

    def test_v3_bytes(self):
        cfg = v3_reference_config()
        table = kv_cache_bytes_per_token(cfg, dtype_bytes=2)
        assert table["mha"] == 65536
        assert table["mla"] == 1152

    def test_compression_improves_with_smaller_latent(self):
        small = MlaConfig(n_heads=16, d_head=32, n_latent=16, n_rope=8)
        large = MlaConfig(n_heads=16, d_head=32, n_latent=64, n_rope=8)
        assert kv_compression_ratio(small) > kv_compression_ratio(large)


class TestReconstruction:
    def test_weight_shapes(self):
        cfg = MlaConfig(n_heads=8, d_head=16, n_latent=12, n_rope=4)
        w = make_mla_weights(cfg, seed=0)
        d_model = 8 * 16
        assert w["dkv"].shape == (d_model, 12)
        assert w["uk"].shape == (12, d_model)
        assert w["uv"].shape == (12, d_model)

    def test_round_trip_shapes(self):
        cfg = MlaConfig(n_heads=4, d_head=8, n_latent=6, n_rope=2)
        w = make_mla_weights(cfg, seed=0)
        h = np.random.default_rng(0).standard_normal((10, 32))
        c = compress_kv(h, w["dkv"])
        assert c.shape == (10, 6)
        k = reconstruct_heads(c, w["uk"], cfg)
        assert k.shape == (10, 4, 8)

    def test_lossless_on_latent_subspace(self):
        """数据恰在潜空间内时重建无损（MLA 压缩的是存储不是表达）。"""
        err = latent_reconstruction_error(noise=0.0)
        assert err < 1e-9

    def test_noisy_reconstruction_small(self):
        err = latent_reconstruction_error(noise=0.05)
        assert 0.0 < err < 0.2

    def test_reconstruction_deterministic(self):
        assert latent_reconstruction_error(seed=1) == latent_reconstruction_error(
            seed=1
        )

    def test_bigger_latent_reduces_error(self):
        cfg_small = MlaConfig(n_latent=8)
        cfg_big = MlaConfig(n_latent=48)
        e_small = latent_reconstruction_error(cfg_small, seed=0)
        e_big = latent_reconstruction_error(cfg_big, seed=0)
        assert e_big < e_small


class TestDSA:
    def _scores(self, seq=32, d=8, seed=0):
        rng = np.random.default_rng(seed)
        q = rng.standard_normal((seq, d))
        k = rng.standard_normal((seq, d))
        w = np.abs(rng.standard_normal(seq))
        return lightning_index_scores(q, k, w), seq

    def test_scores_nonnegative(self):
        scores, _ = self._scores()
        assert scores.min() >= 0.0

    def test_scores_scaled_by_w(self):
        """w_t 放大 ⇒ 对应行整体打分等比放大。"""
        rng = np.random.default_rng(0)
        q = rng.standard_normal((4, 8))
        k = rng.standard_normal((4, 8))
        s1 = lightning_index_scores(q, k, np.ones(4))
        s2 = lightning_index_scores(q, k, np.full(4, 2.0))
        assert np.allclose(s2, 2.0 * s1)

    def test_select_top_k_count(self):
        rng = np.random.default_rng(1)
        scores = rng.random((16, 16))
        mask = select_top_k(scores, 5)
        assert mask.shape == scores.shape
        assert mask.sum() == 16 * 5
        # 每行选中的应是该行分数最高的 5 个
        for i in range(16):
            chosen = set(np.where(mask[i])[0])
            top = set(np.argsort(-scores[i])[:5])
            assert chosen == top

    def test_select_top_k_clamps(self):
        scores = np.random.default_rng(2).random((8, 8))
        mask = select_top_k(scores, 100)
        assert mask.all()

    def test_flops_ratio(self):
        assert sparse_attention_flops_ratio(128 * 1024, 2048) == pytest.approx(
            2048 / (128 * 1024)
        )
        assert sparse_attention_flops_ratio(128 * 1024, 2048) == pytest.approx(1 / 64)

    def test_flops_ratio_requires_positive_seq(self):
        with pytest.raises(ValueError):
            sparse_attention_flops_ratio(0, 8)
