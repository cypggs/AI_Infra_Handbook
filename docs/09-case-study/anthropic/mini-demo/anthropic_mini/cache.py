"""Prompt-cache simulator faithfully modelling Claude's prefix-cache semantics.

Key behaviours reproduced from the official Prompt Caching documentation:

* The prompt prefix is ordered ``tools -> system -> messages``; a cache entry is
  a cumulative hash of everything up to and including a block.
* **Writes happen only at breakpoints.** Marking a block with ``cache_control``
  writes exactly one entry (the prefix hash at that block).
* **Reads look backward.** On a request the system computes the prefix hash at
  each breakpoint and, if it misses, walks backward block by block looking for
  an entry a prior request wrote. The lookback window is **20 blocks**.
* **TTL.** Default 5 minutes; an optional 1-hour cache costs more to write.
  Reading an entry refreshes it for free.
* **Isolation.** Entries are isolated per organization and (on the Claude API /
  Foundry) per workspace.
* **Pricing multipliers.** read = 0.10x, 5m write = 1.25x, 1h write = 2.00x the
  base input price.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field, replace

# --- tunables --------------------------------------------------------------

TTL_5M = 300.0
TTL_1H = 3600.0
LOOKBACK = 20  # the system checks at most 20 positions per breakpoint

READ_MULT = 0.10
WRITE_5M_MULT = 1.25
WRITE_1H_MULT = 2.00


def estimate_tokens(text: str) -> int:
    """A deterministic, dependency-free token estimate (~4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# --- data structures -------------------------------------------------------


@dataclass(frozen=True)
class Block:
    """One cacheable unit of a prompt prefix (a tool / system / message block)."""

    kind: str  # "tool" | "system" | "message"
    text: str
    cache_control: dict | None = None

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)

    @property
    def cache_ttl(self) -> str:
        if self.cache_control and self.cache_control.get("ttl") == "1h":
            return "1h"
        return "5m"

    def with_cache_control(self, cc: dict) -> "Block":
        return replace(self, cache_control=cc)


def cumulative_hashes(blocks: list[Block]) -> list[str]:
    """Cumulative prefix hashes; ``out[i]`` covers ``blocks[0..i]`` inclusive.

    Changing any block changes its own hash and every hash after it.
    """
    acc = ""
    out: list[str] = []
    for b in blocks:
        acc += f"|{b.kind}:{b.text}"
        out.append(hashlib.sha256(acc.encode("utf-8")).hexdigest())
    return out


@dataclass
class Usage:
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0  # total newly written (5m + 1h)
    input_tokens: int = 0  # uncached tokens after the last breakpoint
    write_5m_tokens: int = 0
    write_1h_tokens: int = 0

    @property
    def total_input(self) -> int:
        return (
            self.cache_read_input_tokens
            + self.cache_creation_input_tokens
            + self.input_tokens
        )

    @property
    def hit(self) -> bool:
        return self.cache_read_input_tokens > 0


@dataclass
class _Entry:
    ttl: float
    expiry: float


# --- the cache -------------------------------------------------------------


class PromptCache:
    """An in-memory prefix cache with workspace isolation and TTL."""

    def __init__(self, clock=time.monotonic) -> None:
        self._entries: dict[tuple[str, str], _Entry] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def _now(self) -> float:
        return self._clock()

    def _exists(self, workspace: str, h: str) -> bool:
        key = (workspace, h)
        e = self._entries.get(key)
        if e is None:
            return False
        if e.expiry <= self._now():
            self._entries.pop(key, None)
            return False
        return True

    def _touch(self, workspace: str, h: str) -> None:
        """Refresh an entry on read (free refresh while the cache is in use)."""
        e = self._entries.get((workspace, h))
        if e is not None:
            e.expiry = self._now() + e.ttl

    def _find_hit(self, workspace: str, hashes: list[str], bps: list[int]) -> int | None:
        """Highest index covered by some breakpoint's 20-block lookback that hits."""
        best: int | None = None
        for bp in sorted(set(bps), reverse=True):
            low = bp - (LOOKBACK - 1)
            for i in range(bp, low - 1, -1):
                if i < 0:
                    break
                if self._exists(workspace, hashes[i]):
                    if best is None or i > best:
                        best = i
        return best

    def process(
        self,
        blocks: list[Block],
        breakpoints: list[int] | None = None,
        workspace: str = "default",
    ) -> Usage:
        if not blocks:
            return Usage()

        hashes = cumulative_hashes(blocks)
        tokens = [b.tokens for b in blocks]
        n = len(blocks)

        bps = sorted({bp for bp in (breakpoints or []) if 0 <= bp < n})
        if not bps:  # automatic caching: breakpoint on the last block
            bps = [n - 1]
        last_bp = bps[-1]

        a = self._find_hit(workspace, hashes, bps)
        hit = -1 if a is None else a

        read_tokens = sum(tokens[: hit + 1])
        after_tokens = sum(tokens[last_bp + 1 :])

        # Writes happen at every breakpoint strictly past the highest hit.
        writes = [bp for bp in bps if bp > hit]
        write_5m = write_1h = 0
        prev = hit
        for bp in writes:
            seg = sum(tokens[prev + 1 : bp + 1])
            if blocks[bp].cache_ttl == "1h":
                write_1h += seg
            else:
                write_5m += seg
            prev = bp
        creation = write_5m + write_1h

        with self._lock:
            now = self._now()
            for bp in writes:
                ttl = TTL_1H if blocks[bp].cache_ttl == "1h" else TTL_5M
                self._entries[(workspace, hashes[bp])] = _Entry(ttl=ttl, expiry=now + ttl)
            if a is not None:
                self._touch(workspace, hashes[a])

        return Usage(
            cache_read_input_tokens=read_tokens,
            cache_creation_input_tokens=creation,
            input_tokens=after_tokens,
            write_5m_tokens=write_5m,
            write_1h_tokens=write_1h,
        )


def cost(usage: Usage, base_per_mtok: float) -> float:
    """Estimated cost given a base price per 1M input tokens."""
    m = base_per_mtok / 1_000_000.0
    return (
        usage.cache_read_input_tokens * READ_MULT * m
        + usage.write_5m_tokens * WRITE_5M_MULT * m
        + usage.write_1h_tokens * WRITE_1H_MULT * m
        + usage.input_tokens * m
    )
