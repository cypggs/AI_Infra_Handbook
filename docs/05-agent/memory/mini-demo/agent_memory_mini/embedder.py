from __future__ import annotations

import hashlib
import math
import re
from typing import List


def tokenize(text: str) -> List[str]:
    """Normalize and tokenize text.

    English words and numbers are kept as tokens; every other non-space
    character (for example CJK characters) becomes its own token. This keeps
    the embedder language-agnostic without relying on external tokenizers.
    """
    text = text.lower()
    # Keep ASCII words/numbers and Unicode word characters (e.g. CJK),
    # drop punctuation and whitespace.
    return re.findall(r"[a-z0-9]+|[^\W\s]", text)


class DeterministicEmbedder:
    """Hash-based deterministic text embedder.

    Similar in spirit to scikit-learn's HashingVectorizer: n-gram features are
    hashed into a fixed-dimensional vector. No external dependencies; the same
    input always produces the same unit-norm vector, and semantically similar
    texts tend to receive higher cosine similarity.
    """

    def __init__(self, dim: int = 128, ngram_range: tuple[int, int] = (1, 2)):
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self.ngram_range = ngram_range

    def embed(self, text: str) -> List[float]:
        """Return a unit-norm embedding vector for ``text``."""
        tokens = tokenize(text)
        vec = [0.0] * self.dim
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            if n > len(tokens):
                continue
            for i in range(len(tokens) - n + 1):
                ngram = " ".join(tokens[i : i + n])
                digest = hashlib.md5(ngram.encode("utf-8")).hexdigest()
                idx = int(digest, 16) % self.dim
                sign = 1 if (int(digest[:8], 16) % 2 == 0) else -1
                vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
