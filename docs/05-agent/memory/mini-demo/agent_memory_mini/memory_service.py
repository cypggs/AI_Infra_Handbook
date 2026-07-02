from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from agent_memory_mini.embedder import DeterministicEmbedder
from agent_memory_mini.episodic_memory import EpisodicMemory
from agent_memory_mini.long_term_memory import LongTermMemory
from agent_memory_mini.procedural_memory import ProceduralMemory
from agent_memory_mini.retriever import MemoryRetriever
from agent_memory_mini.short_term_memory import ShortTermMemory
from agent_memory_mini.storage import JsonFileStorage, Storage
from agent_memory_mini.summarizer import SimpleExtractiveSummarizer
from agent_memory_mini.vector_store import InMemoryVectorStore, MemoryRecord
from agent_memory_mini.working_memory import WorkingMemory


class MemoryService:
    """Orchestrates all memory tiers of a small agent memory system.

    MemoryService ties together:

    * ``working`` - the current session message buffer.
    * ``short_term`` - a sliding window of recent turns / session summaries.
    * ``long_term`` - semantic facts and preferences.
    * ``episodic`` - task episodes (goal, actions, outcome).
    * ``procedural`` - reusable patterns / few-shot examples.

    It exposes a single ``remember`` / ``recall`` interface that dispatches to
    the appropriate tier, plus persistence via JSON storage.
    """

    def __init__(self) -> None:
        self.embedder = DeterministicEmbedder()
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(InMemoryVectorStore(), self.embedder)
        self.episodic = EpisodicMemory(InMemoryVectorStore(), self.embedder)
        self.procedural = ProceduralMemory(InMemoryVectorStore(), self.embedder)
        self.retriever = MemoryRetriever(self.embedder, self.long_term.store)
        self.summarizer = SimpleExtractiveSummarizer()
        self.storage: Optional[Storage] = None

    def remember(
        self,
        memory_type: str,
        content: Any,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store ``content`` in the requested memory tier.

        Supported memory types:

        * ``fact`` - ``content`` is a string stored in long-term memory.
        * ``session`` - ``content`` is a dict with ``session_id`` and
          ``messages`` stored as a short-term session summary.
        * ``task`` - ``content`` is a dict with ``goal``, ``actions``, and
          ``outcome`` stored in episodic memory.
        * ``example`` / ``pattern`` - ``content`` is a string or dict stored
          in procedural memory.

        Returns the generated memory id.
        """
        memory_type = memory_type.lower()
        if memory_type == "fact":
            if not isinstance(content, str):
                raise TypeError("fact memory expects a string")
            return self.long_term.remember(content, metadata)

        if memory_type == "session":
            if not isinstance(content, dict):
                raise TypeError("session memory expects a dict")
            session_id = content.get("session_id", "session")
            messages = content.get("messages", [])
            self.short_term.add_session(session_id, messages)
            return session_id

        if memory_type == "task":
            if not isinstance(content, dict):
                raise TypeError("task memory expects a dict")
            return self.episodic.store(
                goal=content["goal"],
                actions=content.get("actions", []),
                outcome=content.get("outcome", ""),
                metadata=metadata,
            )

        if memory_type in ("example", "pattern"):
            return self.procedural.remember(content, metadata)

        raise ValueError(f"Unknown memory_type: {memory_type}")

    def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Recall memories relevant to ``query``.

        ``memory_type`` can be ``fact``, ``task``, ``example``, ``pattern``, or
        ``None`` to search all tiers. Long-term facts use hybrid retrieval
        (vector + keyword); other tiers use vector search.
        """
        target = (memory_type or "all").lower()
        results: List[Dict[str, Any]] = []

        def fmt(record: MemoryRecord, mtype: str) -> Dict[str, Any]:
            return {
                "id": record.id,
                "text": record.text,
                "score": record.score,
                "memory_type": mtype,
                "metadata": record.metadata,
            }

        if target in ("fact", "long_term", "all"):
            for record, score in self.retriever.retrieve(
                query, mode="hybrid", top_k=top_k
            ):
                record.score = score
                results.append(fmt(record, "fact"))

        if target in ("task", "episodic", "all"):
            for record in self.episodic.recall(query, top_k):
                results.append(fmt(record, "task"))

        if target in ("example", "pattern", "procedural", "all"):
            for record in self.procedural.recall(query, top_k):
                results.append(fmt(record, "example"))

        results.sort(key=lambda x: x.get("score") or 0.0, reverse=True)
        return results[:top_k]

    def consolidate(self) -> str:
        """Summarize working memory and move it into short-term memory.

        This is a lightweight version of memory consolidation: the current
        conversation is compressed and the working buffer is cleared.
        """
        messages = self.working.get_messages()
        if not messages:
            return ""
        text = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in messages
            if m["role"] != "system"
        )
        summary = self.summarizer.summarize(text, max_sentences=2)
        if self.short_term.summary:
            self.short_term.summary = f"{self.short_term.summary} {summary}".strip()
        else:
            self.short_term.summary = summary
        self.working.clear()
        return summary

    def forget(
        self,
        id_or_session_id: str,
        memory_type: Optional[str] = None,
    ) -> bool:
        """Remove a memory by id, or a session by session id."""
        if memory_type == "session":
            return self.short_term.forget_session(id_or_session_id)

        if memory_type is None and self.short_term.forget_session(
            id_or_session_id
        ):
            return True

        for store in (
            self.long_term.store,
            self.episodic.vector_store,
            self.procedural.store,
        ):
            if store.delete(id_or_session_id):
                return True
        return False

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the whole memory service to a plain dictionary."""
        return {
            "working": {"messages": self.working.get_messages()},
            "short_term": {
                "summary": self.short_term.summary,
                "recent_turns": self.short_term.recent_turns,
                "sessions": self.short_term.sessions,
            },
            "long_term": self._store_to_dict(self.long_term.store),
            "episodic": self._store_to_dict(self.episodic.vector_store),
            "procedural": self._store_to_dict(self.procedural.store),
        }

    @staticmethod
    def _store_to_dict(store: InMemoryVectorStore) -> Dict[str, Any]:
        return {
            rid: {
                "id": record.id,
                "text": record.text,
                "embedding": record.embedding,
                "metadata": record.metadata,
            }
            for rid, record in store.records.items()
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore the memory service from a plain dictionary."""
        self.working = WorkingMemory()
        for m in data.get("working", {}).get("messages", []):
            self.working.add_message(m["role"], m["content"])

        st = data.get("short_term", {})
        self.short_term = ShortTermMemory()
        self.short_term.summary = st.get("summary", "")
        self.short_term.recent_turns = list(st.get("recent_turns", []))
        self.short_term.sessions = dict(st.get("sessions", {}))

        self.long_term = LongTermMemory(
            InMemoryVectorStore(), self.embedder
        )
        self._load_store(self.long_term.store, data.get("long_term", {}))

        self.episodic = EpisodicMemory(
            InMemoryVectorStore(), self.embedder
        )
        self._load_store(self.episodic.vector_store, data.get("episodic", {}))

        self.procedural = ProceduralMemory(
            InMemoryVectorStore(), self.embedder
        )
        self._load_store(self.procedural.store, data.get("procedural", {}))

        self.retriever = MemoryRetriever(self.embedder, self.long_term.store)

    @staticmethod
    def _load_store(
        store: InMemoryVectorStore, records: Dict[str, Any]
    ) -> None:
        for record in records.values():
            store.add(
                id=record["id"],
                text=record["text"],
                embedding=record["embedding"],
                metadata=record.get("metadata", {}),
            )

    def save(self, path: str) -> None:
        """Persist the memory service to ``path`` as JSON."""
        self.storage = JsonFileStorage(path)
        self.storage.save(self.to_dict(), path)

    def load(self, path: str) -> None:
        """Restore the memory service from the JSON file at ``path``."""
        self.storage = JsonFileStorage(path)
        data = self.storage.load(path)
        self.from_dict(data)
