from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_memory_mini.summarizer import SimpleExtractiveSummarizer


class ShortTermMemory:
    """Sliding-window short-term memory with extractive summarization.

    Recent conversation turns are kept verbatim. When the number of turns
    exceeds ``max_turns``, the oldest half is summarized and the window slides
    forward. Session summaries can also be stored explicitly for multi-session
    recall.
    """

    def __init__(
        self,
        max_turns: int = 5,
        summarizer: Optional[SimpleExtractiveSummarizer] = None,
    ):
        self.max_turns = max_turns
        self.summarizer = summarizer or SimpleExtractiveSummarizer()
        self.summary: str = ""
        self.recent_turns: List[Dict[str, str]] = []
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        """Add a user/assistant turn, summarizing older turns if needed."""
        if len(self.recent_turns) >= self.max_turns:
            # Summarize the oldest half and slide the window.
            n = len(self.recent_turns)
            to_summarize = self.recent_turns[: n // 2]
            self.recent_turns = self.recent_turns[n // 2 :]
            text = " ".join(
                f"User: {t['user']} Assistant: {t['assistant']}"
                for t in to_summarize
            )
            new_summary = self.summarizer.summarize(text, max_sentences=2)
            if self.summary:
                self.summary = f"{self.summary} {new_summary}".strip()
            else:
                self.summary = new_summary
        self.recent_turns.append(
            {"user": user_message, "assistant": assistant_message}
        )

    def get_context(self) -> str:
        """Return the current short-term context as readable text."""
        parts: List[str] = []
        if self.summary:
            parts.append(f"Summary: {self.summary}")
        for turn in self.recent_turns:
            parts.append(f"User: {turn['user']}")
            parts.append(f"Assistant: {turn['assistant']}")
        return "\n".join(parts)

    def add_session(
        self, session_id: str, messages: List[Dict[str, str]]
    ) -> None:
        """Store a summarized view of a whole session."""
        text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        summary = self.summarizer.summarize(text, max_sentences=3)
        self.sessions[session_id] = {
            "summary": summary,
            "messages": list(messages),
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the stored summary and messages for a session, if any."""
        return self.sessions.get(session_id)

    def forget_session(self, session_id: str) -> bool:
        """Remove a stored session summary."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
