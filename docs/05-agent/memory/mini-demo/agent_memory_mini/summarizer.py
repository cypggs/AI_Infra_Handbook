from __future__ import annotations

import re
from typing import List


class SimpleExtractiveSummarizer:
    """Extractive summarizer using in-document word frequency.

    Sentences are scored by the sum of word frequencies in the entire text.
    The top-scoring sentences are returned in their original order.
    """

    def _sentences(self, text: str) -> List[str]:
        # Split on sentence-ending punctuation (Western and Chinese).
        parts = re.split(r"[.!?。！？]+", text)
        return [s.strip() for s in parts if s.strip()]

    def _words(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Return an extractive summary with at most ``max_sentences``."""
        sentences = self._sentences(text)
        if not sentences:
            return ""
        if len(sentences) <= max_sentences:
            return " ".join(sentences)

        freqs: dict[str, int] = {}
        for word in self._words(text):
            freqs[word] = freqs.get(word, 0) + 1

        scored: List[tuple[int, int, str]] = []
        for idx, sentence in enumerate(sentences):
            score = sum(freqs.get(word, 0) for word in self._words(sentence))
            scored.append((score, idx, sentence))

        # Pick the top sentences by score, breaking ties by original order.
        scored.sort(key=lambda x: (-x[0], x[1]))
        top = sorted(scored[:max_sentences], key=lambda x: x[1])
        return " ".join(sentence for _, _, sentence in top)
