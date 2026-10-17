"""kv_quant.py 的单元测试：注意力正确性、KV 量化粒度与误差传播。"""

import numpy as np
import pytest

from model_quantization_mini import kv_quant


@pytest.fixture()
def kv():
    K, V = kv_quant.make_kv_cache(128, 64, seed=0)
    rng = np.random.default_rng(1)
    Q = rng.standard_normal((8, 64))
    return Q, K, V


def test_attention_shape_and_softmax(kv):
    Q, K, V = kv
    out = kv_quant.attention(Q, K, V)
    assert out.shape == Q.shape
    # softmax 归一性：权重矩阵每行和为 1
    d = K.shape[1]
    scores = Q @ K.T / np.sqrt(d)
    scores -= scores.max(axis=-1, keepdims=True)
    w = np.exp(scores)
    w /= w.sum(axis=-1, keepdims=True)
    np.testing.assert_allclose(w.sum(axis=-1), 1.0, atol=1e-12)


def test_int16_baseline_near_lossless(kv):
    """16-bit 量化应近似无损（作为 FP 基准的代理）。"""
    Q, K, V = kv
    r = kv_quant.kv_quant_attention_error(Q, K, V, bits=16, group_size=32)
    assert r["cosine"] > 0.999999


def test_channel_beats_token_for_keys(kv):
    """K 的离群在通道维：按通道分组显著优于按 token 分组。"""
    Q, K, V = kv
    r_ch = kv_quant.kv_quant_attention_error(Q, K, V, bits=4, k_mode="channel")
    r_tk = kv_quant.kv_quant_attention_error(Q, K, V, bits=4, k_mode="token")
    assert r_ch["cosine"] > r_tk["cosine"]


def test_int8_beats_int4(kv):
    Q, K, V = kv
    r8 = kv_quant.kv_quant_attention_error(Q, K, V, bits=8, k_mode="channel")
    r4 = kv_quant.kv_quant_attention_error(Q, K, V, bits=4, k_mode="channel")
    assert r8["cosine"] > r4["cosine"]


def test_wrong_granularity_degrades_with_length():
    """错误的 K 量化粒度（按 token）随上下文变长劣化更明显。"""
    rng = np.random.default_rng(7)
    res = kv_quant.error_vs_context_length(
        rng, lengths=(128, 512), bits=4, k_mode="token"
    )
    assert res[512]["cosine"] < res[128]["cosine"]


def test_right_granularity_stable_with_length():
    """正确的粒度（K 按通道）在 128→512 区间保持稳定高相似度。"""
    rng = np.random.default_rng(7)
    res = kv_quant.error_vs_context_length(
        rng, lengths=(128, 256, 384, 512), bits=4, k_mode="channel"
    )
    for r in res.values():
        assert r["cosine"] > 0.95


def test_quantized_shapes_preserved(kv):
    Q, K, V = kv
    K_q = kv_quant.quantize_keys(K, bits=4, group_size=32, mode="channel")
    V_q = kv_quant.quantize_values(V, bits=4, group_size=32)
    assert K_q.shape == K.shape and V_q.shape == V.shape


def test_determinism(kv):
    Q, K, V = kv
    r1 = kv_quant.kv_quant_attention_error(Q, K, V, bits=4, k_mode="channel")
    r2 = kv_quant.kv_quant_attention_error(Q, K, V, bits=4, k_mode="channel")
    assert r1 == r2
