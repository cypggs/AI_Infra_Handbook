"""Tests for the deterministic embedder."""

from rag_mini.documents import Chunk, load_chunks
from rag_mini.embedder import Embedder


def test_embedder_determinism():
    chunks = load_chunks()
    embedder1 = Embedder(chunks)
    embedder2 = Embedder(chunks)
    vec1 = embedder1.embed_text("return policy")
    vec2 = embedder2.embed_text("return policy")
    assert vec1 == vec2


def test_embed_query_matches_embed_text():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    query = "What is the return policy?"
    assert embedder.embed_query(query) == embedder.embed_text(query)


def test_embed_chunk_shape():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    embedded = embedder.get_embedded_chunks()
    assert len(embedded) == len(chunks)
    vocab_size = embedder.vocab_size
    for item in embedded:
        assert len(item.vector) == vocab_size
        assert item.token_count > 0
        assert item.term_freq


def test_embed_text_empty():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    vector = embedder.embed_text("")
    assert all(v == 0.0 for v in vector)


def test_embedder_default_corpus():
    embedder = Embedder()
    assert embedder.vocab_size > 0
    assert len(embedder.get_embedded_chunks()) > 0


def test_embedded_chunk_metadata():
    chunks = load_chunks()
    embedder = Embedder(chunks)
    item = embedder.get_embedded_chunks()[0]
    assert isinstance(item.chunk, Chunk)
    assert item.chunk.source
    assert item.chunk.section
