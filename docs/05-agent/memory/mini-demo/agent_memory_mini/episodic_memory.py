from __future__ import annotations

from typing import List, Optional

from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.vector_store import InMemoryVectorStore, MemoryRecord


class EpisodicMemory:
    """Memory for task episodes: a goal, the actions taken, and the outcome."""

    def __init__(
        self,
        vector_store: InMemoryVectorStore,
        embedder: DeterministicEmbedder,
    ):
        self.vector_store = vector_store
        self.embedder = embedder

    def _serialize(
        self, goal: str, actions: List[str], outcome: str
    ) -> str:
        return (
            f"Goal: {goal}\n"
            f"Actions: {', '.join(actions)}\n"
            f"Outcome: {outcome}"
        )

    def store(
        self,
        goal: str,
        actions: List[str],
        outcome: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store an episode and return its generated id."""
        text = self._serialize(goal, actions, outcome)
        memory_id = f"ep-{len(self.vector_store.records)}"
        self.vector_store.add(
            id=memory_id,
            text=text,
            embedding=self.embedder.embed(text),
            metadata=metadata if metadata is not None else {},
        )
        return memory_id

    def recall(self, query: str, top_k: int = 5) -> List[MemoryRecord]:
        """Find episodes semantically similar to ``query``."""
        query_emb = self.embedder.embed(query)
        return self.vector_store.search(query_emb, top_k)
