"""A toy, fully deterministic "embedding inference service".

It mimics the *semantics* of a real embedding server (batch encode,
normalization, dimension control, token truncation) without any neural
network:

- text -> lowercase alphanumeric tokens (CJK character runs count as one
  token, like a unigram sentence-piece)
- each token is hashed (md5) into a fixed-dimension space and the
  corresponding bin is incremented (feature hashing / bag-of-words)
- bigrams are hashed the same way, adding a little word-order signal
- rows are optionally L2-normalized, like most production embedding APIs

Because everything is hash-based, the same text always yields the same
vector across runs and machines — which is exactly what a testable
demo needs. Texts that share tokens/bigrams land near each other
(the overlap / Jaccard signal), not because a model "understands" them.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Sequence, Union

import numpy as np

from .metric import normalize

# latin/digit tokens, or runs of CJK characters treated as one token
_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]+")


def _tokenize(text: str, max_tokens: int) -> List[str]:
    toks = _TOKEN_RE.findall(text.lower())
    return toks[:max_tokens]


def _hash_to(token: str, dim: int) -> int:
    """md5 hash of a token -> index in [0, dim)."""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dim


def _embed_one(text: str, dim: int, max_tokens: int) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float64)
    toks = _tokenize(text, max_tokens)
    for t in toks:
        vec[_hash_to(t, dim)] += 1.0
    for a, b in zip(toks, toks[1:]):  # bigrams for light word-order signal
        vec[_hash_to(a + "_" + b, dim)] += 1.0
    return vec


class ToyEmbeddingServer:
    """Deterministic stand-in for TEI / Infinity-style embedding services.

    Parameters
    ----------
    dim:
        Output vector dimension (like an embedding model's hidden size).
        The default 256 keeps hash collisions rare for small corpora.
    normalize_embeddings:
        L2-normalize rows (the default for cosine-similarity deployments).
    max_tokens:
        Token truncation limit, mimicking an inference server's context cap.
    batch_size:
        Internal "micro-batch" size; encodes are chunked through it just as
        a real server would batch requests (visible via ``batches_served``).
    """

    def __init__(
        self,
        dim: int = 256,
        normalize_embeddings: bool = True,
        max_tokens: int = 64,
        batch_size: int = 8,
    ) -> None:
        if dim < 2:
            raise ValueError("dim must be >= 2")
        self.dim = dim
        self.normalize_embeddings = normalize_embeddings
        self.max_tokens = max_tokens
        self.batch_size = max(1, batch_size)
        self.batches_served = 0  # observability hook, like a request counter

    def encode(
        self, texts: Union[str, Sequence[str]]
    ) -> np.ndarray:
        """Encode one text or a batch of texts -> (n, dim) float64."""
        single = isinstance(texts, str)
        batch = [texts] if single else list(texts)
        rows = []
        for start in range(0, len(batch), self.batch_size):
            chunk = batch[start : start + self.batch_size]
            self.batches_served += 1
            for t in chunk:
                rows.append(_embed_one(t, self.dim, self.max_tokens))
        out = np.vstack(rows) if rows else np.zeros((0, self.dim))
        if self.normalize_embeddings:
            out = normalize(out)
        return out[0] if single else out

    def __call__(self, texts: Union[str, Sequence[str]]) -> np.ndarray:
        return self.encode(texts)


def demo_documents() -> List[dict]:
    """Small multilingual-ish document set used by the demo scenarios."""
    return [
        {"id": 0, "lang": "en", "category": "docs",
         "text": "vector database stores embeddings for similarity search"},
        {"id": 1, "lang": "en", "category": "docs",
         "text": "hnsw is a graph index for approximate nearest neighbor search"},
        {"id": 2, "lang": "en", "category": "ops",
         "text": "milvus shards data across query nodes for horizontal scale"},
        {"id": 3, "lang": "en", "category": "ops",
         "text": "pgvector adds hnsw and ivfflat indexes to postgresql"},
        {"id": 4, "lang": "zh", "category": "docs",
         "text": "向量数据库 存储 embedding 向量 支持 相似度 检索"},
        {"id": 5, "lang": "zh", "category": "ops",
         "text": "量化 技术 压缩 向量 索引 降低 内存 成本"},
        {"id": 6, "lang": "en", "category": "model",
         "text": "embedding models convert text into dense vector representations"},
        {"id": 7, "lang": "zh", "category": "model",
         "text": "bge m3 模型 支持 稠密 稀疏 多向量 混合检索"},
        {"id": 8, "lang": "en", "category": "model",
         "text": "reranker cross encoder rescores retrieved candidates"},
        {"id": 9, "lang": "zh", "category": "docs",
         "text": "磁盘索引 diskann 把 图 索引 放到 ssd 上 降低成本"},
    ]
