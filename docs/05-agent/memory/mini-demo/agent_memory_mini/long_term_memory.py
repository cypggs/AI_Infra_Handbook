from __future__ import annotations

from typing import List, Optional

from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.vector_store import InMemoryVectorStore, MemoryRecord

ACTIVE = "active"
SUPERSEDED = "superseded"
MERGED = "merged"


class LongTermMemory:
    """Semantic long-term memory for facts, preferences, and beliefs.

    Supports Dream/Graphiti-style lifecycle states: facts are never
    physically overwritten; an update *supersedes* the old record (marking
    it with ``lifecycle_state="superseded"``) and writes a new one, so the
    history of a fact is preserved for audit and temporal queries.
    """

    def __init__(
        self,
        vector_store: InMemoryVectorStore,
        embedder: DeterministicEmbedder,
    ):
        self.store = vector_store
        self.embedder = embedder
        self._version = 0

    def remember(self, fact: str, metadata: Optional[dict] = None) -> str:
        """Store a textual fact and return its generated id."""
        memory_id = f"fact-{len(self.store.records)}"
        embedding = self.embedder.embed(fact)
        meta = dict(metadata) if metadata is not None else {}
        meta.setdefault("lifecycle_state", ACTIVE)
        meta.setdefault("valid_from", self._version)
        self._version += 1
        self.store.add(
            id=memory_id,
            text=fact,
            embedding=embedding,
            metadata=meta,
        )
        return memory_id

    def recall(
        self,
        query: str,
        top_k: int = 5,
        latest_only: bool = False,
    ) -> List[MemoryRecord]:
        """Find facts semantically similar to ``query``.

        With ``latest_only=True`` records superseded or merged by
        ``update_fact`` / ``consolidate`` are hidden from the results,
        mirroring Mem0's ``latest_only`` / Graphiti's "currently valid" query.
        """
        query_emb = self.embedder.embed(query)
        total = len(self.store.records)
        records = (
            self.store.search(query_emb, top_k=total) if total else []
        )
        if latest_only:
            records = [
                r
                for r in records
                if r.metadata.get("lifecycle_state", ACTIVE) == ACTIVE
            ]
        return records[:top_k]

    def update_fact(self, memory_id: str, new_text: str) -> str:
        """Supersede ``memory_id`` and store ``new_text`` as its replacement.

        The old record is kept with ``lifecycle_state="superseded"``,
        ``valid_until`` and ``replaced_by`` metadata; the new record becomes
        the active version. Returns the new memory id.
        """
        old = self.store.get(memory_id)
        if old is None:
            raise KeyError(f"unknown memory_id: {memory_id}")
        new_id = self.remember(
            new_text,
            metadata={
                "supersedes": memory_id,
                "lifecycle_state": ACTIVE,
                "valid_from": self._version,
            },
        )
        old.metadata["lifecycle_state"] = SUPERSEDED
        old.metadata["valid_until"] = self._version
        old.metadata["replaced_by"] = new_id
        return new_id

    def consolidate(self) -> List[str]:
        """Mark exact-duplicate facts as merged, keeping the first occurrence.

        This is a deterministic, teaching-grade version of Mem0 Dream's
        merge step: only *identical* text is merged (real systems use LLM
        paraphrase detection). Returns the ids of merged records.
        """
        merged: List[str] = []
        seen: dict[str, str] = {}
        for record in self.store.records.values():
            state = record.metadata.get("lifecycle_state", ACTIVE)
            if state != ACTIVE:
                continue
            if record.text in seen:
                record.metadata["lifecycle_state"] = MERGED
                record.metadata["merged_into"] = seen[record.text]
                merged.append(record.id)
            else:
                seen[record.text] = record.id
        return merged
