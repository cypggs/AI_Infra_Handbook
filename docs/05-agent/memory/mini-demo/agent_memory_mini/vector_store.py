from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MemoryRecord:
    """A single record stored in a vector store."""

    id: str
    text: str
    embedding: List[float]
    metadata: dict = field(default_factory=dict)
    score: Optional[float] = None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """Simple in-memory vector store indexed by cosine similarity."""

    def __init__(self) -> None:
        self.records: Dict[str, MemoryRecord] = {}

    def add(
        self,
        id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[dict] = None,
    ) -> MemoryRecord:
        """Add or overwrite a record."""
        record = MemoryRecord(
            id=id,
            text=text,
            embedding=embedding,
            metadata=metadata if metadata is not None else {},
        )
        self.records[id] = record
        return record

    def search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[MemoryRecord]:
        """Return the ``top_k`` records most similar to the query embedding."""
        scored: List[tuple[float, MemoryRecord]] = []
        for record in self.records.values():
            score = _cosine_similarity(query_embedding, record.embedding)
            record.score = score
            scored.append((score, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:top_k]]

    def delete(self, id: str) -> bool:
        """Remove a record by id. Returns ``True`` if it existed."""
        if id in self.records:
            del self.records[id]
            return True
        return False

    def get(self, id: str) -> Optional[MemoryRecord]:
        """Fetch a record by id, or ``None`` if missing."""
        return self.records.get(id)
