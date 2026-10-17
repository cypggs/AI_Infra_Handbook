"""Personal memory layer: episode store + user profile + deterministic retrieval.

This mirrors how production personal agents split memory:
- episodic memory: timestamped observations (what happened, when);
- profile memory: distilled facts about the user (what is true about you);
- retrieval: keyword-overlap recall across both, with provenance kept.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]+")
_CJK_RE = re.compile(r"[一-鿿]+")
# "记住：key=value" / "记住:key=value" written naturally by the user.
_REMEMBER_RE = re.compile(r"记住\s*[:：]\s*([^=，,；;]+?)\s*[=＝]\s*(.+)$")


def _terms(text: str) -> list[str]:
    """Latin words stay whole; CJK runs become character bigrams."""
    terms: list[str] = []
    for tok in _TOKEN_RE.findall(text.lower()):
        if _CJK_RE.fullmatch(tok):
            if len(tok) == 1:
                terms.append(tok)
            else:
                terms.extend(tok[i:i + 2] for i in range(len(tok) - 1))
        else:
            terms.append(tok)
    return terms


@dataclass
class Episode:
    id: str
    kind: str  # user / agent / email / calendar / files / system
    content: str
    ts: datetime
    tags: tuple[str, ...] = ()
    day: str = ""

    def matches(self, terms: list[str]) -> int:
        haystack = self.content.lower()
        return sum(1 for t in set(terms) if t in haystack)


@dataclass
class ProfileFact:
    key: str
    value: str
    source: str = ""  # episode id that produced the fact, "" if explicit
    created: datetime | None = None


class PersonalMemory:
    """Episode store plus a derived user profile with full provenance."""

    def __init__(self) -> None:
        self._episodes: list[Episode] = []
        self._facts: dict[str, ProfileFact] = {}
        self._counter = 0

    # ---------- episodic store ----------

    def add_episode(self, kind: str, content: str, ts: datetime, tags=()) -> Episode:
        self._counter += 1
        ep = Episode(
            id=f"ep{self._counter}",
            kind=kind,
            content=content,
            ts=ts,
            tags=tuple(tags),
            day=ts.date().isoformat(),
        )
        self._episodes.append(ep)
        self._extract_profile(ep)
        return ep

    def episodes(self) -> list[Episode]:
        return list(self._episodes)

    def get(self, episode_id: str) -> Episode:
        for ep in self._episodes:
            if ep.id == episode_id:
                return ep
        raise KeyError(episode_id)

    def delete_episode(self, episode_id: str) -> None:
        self._episodes = [ep for ep in self._episodes if ep.id != episode_id]

    def recall_day(self, day: str) -> list[Episode]:
        return [ep for ep in self._episodes if ep.day == day]

    # ---------- profile ----------

    def remember(self, key: str, value: str, ts: datetime, source_episode: Episode | None = None) -> ProfileFact:
        fact = ProfileFact(
            key=key.strip(),
            value=value.strip(),
            source=source_episode.id if source_episode else "",
            created=ts,
        )
        self._facts[fact.key] = fact
        return fact

    def forget(self, key: str) -> bool:
        return self._facts.pop(key, None) is not None

    def profile(self) -> dict[str, ProfileFact]:
        return dict(self._facts)

    def _extract_profile(self, ep: Episode) -> None:
        m = _REMEMBER_RE.search(ep.content)
        if m and ep.kind == "user":
            self.remember(m.group(1), m.group(2), ep.ts, ep)

    def profile_match(self, query: str) -> list[ProfileFact]:
        terms = _terms(query)
        hits: list[tuple[int, ProfileFact]] = []
        for key, fact in self._facts.items():
            bucket = f"{key} {fact.value}".lower()
            score = sum(1 for t in set(terms) if t in bucket)
            if score > 0:
                hits.append((score, fact))
        hits.sort(key=lambda x: (-x[0], x[1].key))
        return [f for _, f in hits]

    # ---------- retrieval ----------

    def recall(self, query: str, limit: int = 3, kind: str | None = None) -> list[Episode]:
        terms = _terms(query)
        scored: list[tuple[int, Episode]] = []
        for ep in self._episodes:
            if kind is not None and ep.kind != kind:
                continue
            score = ep.matches(terms)
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [ep for _, ep in scored[:limit]]
