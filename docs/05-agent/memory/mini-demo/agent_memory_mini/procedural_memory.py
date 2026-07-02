from __future__ import annotations

import json
from typing import Any, List, Optional

from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.vector_store import InMemoryVectorStore, MemoryRecord


class ProceduralMemory:
    """Memory for reusable tool-call patterns and few-shot examples."""

    def __init__(
        self,
        vector_store: InMemoryVectorStore,
        embedder: DeterministicEmbedder,
    ):
        self.store = vector_store
        self.embedder = embedder

    def _serialize(self, pattern: Any) -> str:
        if isinstance(pattern, str):
            return pattern
        if isinstance(pattern, dict):
            if "description" in pattern:
                return str(pattern["description"])
            return json.dumps(pattern, ensure_ascii=False, sort_keys=True)
        return str(pattern)

    def remember(self, pattern: Any, metadata: Optional[dict] = None) -> str:
        """Store a pattern/example and return its generated id."""
        text = self._serialize(pattern)
        memory_id = f"proc-{len(self.store.records)}"
        self.store.add(
            id=memory_id,
            text=text,
            embedding=self.embedder.embed(text),
            metadata=metadata if metadata is not None else {},
        )
        return memory_id

    def recall(self, query: str, top_k: int = 5) -> List[MemoryRecord]:
        """Find patterns semantically similar to ``query``."""
        query_emb = self.embedder.embed(query)
        return self.store.search(query_emb, top_k)
