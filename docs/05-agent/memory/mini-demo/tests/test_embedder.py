import math

from agent_memory_mini.embedder import DeterministicEmbedder, tokenize


def test_tokenize_handles_chinese_and_english():
    assert tokenize("我喜欢 Python") == ["我", "喜", "欢", "python"]
    assert tokenize("Hello, world!") == ["hello", "world"]


def test_embedding_is_deterministic_and_unit_norm():
    embedder = DeterministicEmbedder(dim=64)
    a = embedder.embed("hello world")
    b = embedder.embed("hello world")
    assert a == b
    assert len(a) == 64
    norm = math.sqrt(sum(v * v for v in a))
    assert math.isclose(norm, 1.0, rel_tol=1e-9)


def test_similarity_ordering():
    embedder = DeterministicEmbedder(dim=64)
    v1 = embedder.embed("python programming language")
    v2 = embedder.embed("python code")
    v3 = embedder.embed("coffee shop menu")
    assert embedder.similarity(v1, v2) > embedder.similarity(v1, v3)


def test_empty_text_embedding():
    embedder = DeterministicEmbedder(dim=32)
    vec = embedder.embed("")
    assert vec == [0.0] * 32
    assert embedder.similarity(vec, embedder.embed("hello")) == 0.0
