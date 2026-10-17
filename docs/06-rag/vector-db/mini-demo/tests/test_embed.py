import numpy as np
import pytest

from vector_db_mini.embed import ToyEmbeddingServer, _hash_to, _tokenize, demo_documents


def test_tokenize_lowercase_and_cjk():
    assert _tokenize("Hello, WORLD 123", 64) == ["hello", "world", "123"]
    assert _tokenize("向量数据库 Vector DB", 64) == ["向量数据库", "vector", "db"]


def test_tokenize_max_tokens():
    toks = _tokenize("a b c d e", 3)
    assert toks == ["a", "b", "c"]


def test_hash_to_deterministic_and_in_range():
    i1 = _hash_to("hello", 64)
    i2 = _hash_to("hello", 64)
    assert i1 == i2
    assert 0 <= i1 < 64


def test_encode_fixed_dim():
    server = ToyEmbeddingServer(dim=32)
    v = server.encode("some text")
    assert v.shape == (32,)


def test_encode_batch_shape_and_single_equivalence():
    server = ToyEmbeddingServer(dim=16)
    batch = server.encode(["alpha text", "beta words", "gamma"])
    assert batch.shape == (3, 16)
    single = server.encode("beta words")
    np.testing.assert_array_equal(batch[1], single)


def test_encode_is_deterministic_across_instances():
    a = ToyEmbeddingServer(dim=32).encode("向量检索 vector search")
    b = ToyEmbeddingServer(dim=32).encode("向量检索 vector search")
    np.testing.assert_array_equal(a, b)


def test_normalized_rows_are_unit_norm():
    server = ToyEmbeddingServer(dim=16, normalize_embeddings=True)
    out = server.encode(["some words", "other stuff"])
    norms = np.linalg.norm(out, axis=1)
    np.testing.assert_allclose(norms, 1.0, rtol=1e-9)


def test_empty_text_zero_vector():
    server = ToyEmbeddingServer(dim=8, normalize_embeddings=False)
    v = server.encode("")
    assert np.all(v == 0.0)


def test_max_tokens_truncation_changes_result():
    full = ToyEmbeddingServer(dim=32, max_tokens=64, normalize_embeddings=False)
    trunc = ToyEmbeddingServer(dim=32, max_tokens=1, normalize_embeddings=False)
    text = "alpha beta gamma delta"
    np.testing.assert_array_equal(trunc.encode(text), full.encode("alpha"))


def test_batches_served_counter():
    server = ToyEmbeddingServer(dim=8, batch_size=2)
    server.encode(["a", "b", "c", "d", "e"])
    assert server.batches_served == 3  # 2+2+1


def test_similar_texts_closer_than_unrelated():
    server = ToyEmbeddingServer(dim=64)
    v1 = server.encode("vector database similarity search")
    v2 = server.encode("vector database index search")
    v3 = server.encode("apple banana orange fruit salad")
    from vector_db_mini.metric import l2_distance

    d_close = l2_distance(v1, v2)[0, 0]
    d_far = l2_distance(v1, v3)[0, 0]
    assert d_close < d_far


def test_demo_documents_have_languages():
    docs = demo_documents()
    assert len(docs) >= 8
    assert any(d["lang"] == "zh" for d in docs)
    assert any(d["lang"] == "en" for d in docs)
    ids = [d["id"] for d in docs]
    assert len(set(ids)) == len(ids)
