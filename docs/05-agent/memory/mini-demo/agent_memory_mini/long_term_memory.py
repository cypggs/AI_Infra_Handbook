from __future__ import annotations

from typing import List, Optional

from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.vector_store import InMemoryVectorStore, MemoryRecord


class LongTermMemory:
    """Semantic long-term memory for facts, preferences, and beliefs."""

    def __init__(
        self,
        vector_store: InMemoryVectorStore,
        embedder: DeterministicEmbedder,
    ):
        self.store = vector_store
        self.embedder = embedder

    def remember(self, fact: str, metadata: Optional[dict] = None) -> str:
        """Store a textual fact and return its generated id."""
        memory_id = f"fact-{len(self.store.records)}"
        embedding = self.embedder.embed(fact)
        self.store.add(
            id=memory_id,
            text=fact,
            embedding=embedding,
            metadata=metadata if metadata is not None else {},
        )
        return memory_id

    def recall(self, query: str, top_k: int = 5) -> List[MemoryRecord]:
        """Find facts semantically similar to ``query``."""
        query_emb = self.embedder.embed(query)
        return self.store.search(query_emb, top_k)
