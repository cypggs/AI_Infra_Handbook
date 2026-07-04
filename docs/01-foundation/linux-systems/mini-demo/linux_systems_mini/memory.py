"""Page cache LRU and OOM killer simulator."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Page:
    """A page in the page cache."""
    page_id: int
    owner: int  # pid that allocated/loaded it
    size: int = 1  # abstract page size units


@dataclass
class PageCache:
    """Simplified page cache with LRU eviction."""
    capacity: int  # max page units
    pages: "OrderedDict[int, Page]" = field(default_factory=OrderedDict)
    hits: int = 0
    misses: int = 0

    def access(self, page_id: int, owner: int) -> bool:
        """Access a page. Returns True on hit, False on miss."""
        if page_id in self.pages:
            self.pages.move_to_end(page_id)
            self.hits += 1
            return True
        self.misses += 1
        self._load(page_id, owner)
        return False

    def _load(self, page_id: int, owner: int) -> None:
        while self.used + 1 > self.capacity:
            self._evict_lru()
        self.pages[page_id] = Page(page_id=page_id, owner=owner)
        self.pages.move_to_end(page_id)

    def _evict_lru(self) -> Page:
        if not self.pages:
            raise RuntimeError("Cannot evict from empty cache")
        page_id, page = self.pages.popitem(last=False)
        return page

    @property
    def used(self) -> int:
        return sum(p.size for p in self.pages.values())

    def per_owner_usage(self) -> Dict[int, int]:
        usage: Dict[int, int] = {}
        for page in self.pages.values():
            usage[page.owner] = usage.get(page.owner, 0) + page.size
        return usage


@dataclass
class ProcessMemory:
    """Memory accounting for a process."""
    pid: int
    name: str
    rss: int = 0  # resident pages
    nice: int = 0
    runtime: float = 0.0  # seconds since start
    oom_score_adj: int = 0


@dataclass
class OOMKiller:
    """Simplified OOM killer scoring."""
    processes: List[ProcessMemory] = field(default_factory=list)

    def score(self, proc: ProcessMemory) -> float:
        """Higher score = more likely to be killed."""
        # rss is the dominant factor
        score = float(proc.rss)
        # longer runtime makes a process slightly more "important"
        if proc.runtime > 0:
            score /= (1.0 + proc.runtime / 1000.0)
        # nicer processes are less critical; lower nice -> subtract more
        score -= proc.nice * 5.0
        score += proc.oom_score_adj
        return max(score, 1.0)

    def pick_victim(self) -> ProcessMemory | None:
        if not self.processes:
            return None
        return max(self.processes, key=lambda p: self.score(p))
