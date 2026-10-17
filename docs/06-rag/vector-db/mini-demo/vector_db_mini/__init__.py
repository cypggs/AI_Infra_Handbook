"""vector_db_mini: a tiny, CPU-runnable vector search stack.

Modules
-------
metric    : l2 / inner-product / cosine distances (smaller-is-better convention)
quantize  : ScalarQuantizer + ProductQuantizer (deterministic, seeded)
index     : FlatIndex / IVFFlatIndex / HNSWIndex (simplified, deterministic)
embed     : ToyEmbeddingServer — hash-based deterministic embedding service
demo      : end-to-end comparison scenarios
"""

from .embed import ToyEmbeddingServer, demo_documents
from .index import FlatIndex, HNSWIndex, IVFFlatIndex, SearchResult
from .metric import METRICS, cosine_distance, inner_product, l2_distance, normalize
from .quantize import ProductQuantizer, ScalarQuantizer

__version__ = "0.1.0"

__all__ = [
    "METRICS",
    "FlatIndex",
    "HNSWIndex",
    "IVFFlatIndex",
    "ProductQuantizer",
    "ScalarQuantizer",
    "SearchResult",
    "ToyEmbeddingServer",
    "cosine_distance",
    "demo_documents",
    "inner_product",
    "l2_distance",
    "normalize",
]
