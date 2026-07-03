"""Deterministic embedder and keyword index for the RAG mini demo.

This module avoids external ML libraries.  It builds a fixed vocabulary from the
static corpus and represents each chunk as a bag-of-words vector.  A keyword
index supports simple BM25-like retrieval without any neural model.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from rag_mini.documents import Chunk, load_chunks


@dataclass(frozen=True)
class EmbeddedChunk:
    """A chunk plus its dense vector and term frequency statistics."""

    chunk: Chunk
    vector: list[float]
    term_freq: dict[str, int]
    token_count: int


def _tokenize(text: str) -> list[str]:
    """Lower-case and tokenize a text into alphanumeric words."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_vocabulary(chunks: list[Chunk]) -> list[str]:
    """Return a deterministic sorted vocabulary from all chunk texts."""
    vocab: set[str] = set()
    for chunk in chunks:
        vocab.update(_tokenize(chunk.text))
    return sorted(vocab)


def _compute_idf(chunks: list[Chunk], vocab: list[str]) -> dict[str, float]:
    """Compute inverse document frequency for each vocabulary term."""
    n = len(chunks)
    doc_freq: dict[str, int] = {term: 0 for term in vocab}
    for chunk in chunks:
        terms = set(_tokenize(chunk.text))
        for term in terms:
            if term in doc_freq:
                doc_freq[term] += 1
    return {term: math.log((n + 1) / (df + 1)) + 1 for term, df in doc_freq.items()}


class Embedder:
    """Deterministic TF-IDF embedder built from the static Acme Corp corpus."""

    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        self._chunks = chunks if chunks is not None else load_chunks()
        self._vocab = _build_vocabulary(self._chunks)
        self._idf = _compute_idf(self._chunks, self._vocab)
        self._vocab_index = {term: idx for idx, term in enumerate(self._vocab)}
        self._embedded = [self.embed_chunk(chunk) for chunk in self._chunks]

    @property
    def vocabulary(self) -> list[str]:
        return list(self._vocab)

    @property
    def vocab_size(self) -> int:
        """Return the number of terms in the vocabulary."""
        return len(self._vocab)

    @property
    def idf(self) -> dict[str, float]:
        return dict(self._idf)

    def embed_text(self, text: str) -> list[float]:
        """Return a normalized TF-IDF vector for an arbitrary text."""
        tokens = _tokenize(text)
        counts = Counter(tokens)
        vector = [0.0] * len(self._vocab)
        for term, count in counts.items():
            idx = self._vocab_index.get(term)
            if idx is not None:
                vector[idx] = count * self._idf[term]
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def embed_chunk(self, chunk: Chunk) -> EmbeddedChunk:
        """Embed a single chunk and pre-compute keyword statistics."""
        vector = self.embed_text(chunk.text)
        tokens = _tokenize(chunk.text)
        return EmbeddedChunk(
            chunk=chunk,
            vector=vector,
            term_freq=dict(Counter(tokens)),
            token_count=len(tokens),
        )

    def embed_chunks(self, chunks: Iterable[Chunk]) -> list[EmbeddedChunk]:
        return [self.embed_chunk(chunk) for chunk in chunks]

    def embed_query(self, query: str) -> list[float]:
        """Embed a user query using the same TF-IDF representation."""
        return self.embed_text(query)

    def get_embedded_chunks(self) -> list[EmbeddedChunk]:
        """Return all pre-computed embedded chunks."""
        return list(self._embedded)
