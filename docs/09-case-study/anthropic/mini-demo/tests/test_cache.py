"""Tests for the prompt-cache simulator."""

from __future__ import annotations

import pytest

from anthropic_mini.cache import (
    Block,
    PromptCache,
    TTL_5M,
    TTL_1H,
    Usage,
    cost,
    cumulative_hashes,
    estimate_tokens,
)


class FakeClock:
    """A controllable monotonic clock for deterministic TTL tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def tick(self, seconds: float) -> None:
        self.t += seconds


def tok(kind: str, n: int, cc: dict | None = None) -> Block:
    """Build a block whose estimated token count is exactly ``n``."""
    assert n >= 1
    return Block(kind, "x" * (4 * n), cc)


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("x" * 4) == 1
    assert estimate_tokens("x" * 7) == 1  # 7 // 4 == 1
    assert estimate_tokens("x" * 8) == 2


def test_cumulative_hashes_change_on_edit() -> None:
    blocks = [tok("system", 10), tok("message", 5)]
    h = cumulative_hashes(blocks)
    assert h[0] != h[1]
    # editing block 0 changes both hashes
    edited = cumulative_hashes([tok("system", 11), tok("message", 5)])
    assert edited[0] != h[0]
    assert edited[1] != h[1]


def test_first_write_then_hit() -> None:
    cache = PromptCache(clock=FakeClock())
    blocks = [tok("system", 100), tok("message", 20), tok("message", 5)]
    bp = 1  # cache system + first message; the 5-token message is the suffix

    first = cache.process(blocks, [bp], workspace="t")
    assert first.cache_read_input_tokens == 0
    assert first.cache_creation_input_tokens == 120  # 100 + 20
    assert first.input_tokens == 5  # after the breakpoint
    assert not first.hit

    second = cache.process(blocks, [bp], workspace="t")
    assert second.cache_read_input_tokens == 120
    assert second.cache_creation_input_tokens == 0
    assert second.input_tokens == 5
    assert second.hit


def test_varying_suffix_trap() -> None:
    """Putting cache_control on a block that changes every request => never a hit."""
    cache = PromptCache(clock=FakeClock())

    # Request 1: timestamp block is the breakpoint.
    blocks1 = [tok("system", 100), tok("message", 5, {"type": "ephemeral"})]
    cache.process(blocks1, [1], workspace="t")

    # Request 2: timestamp differs -> different prefix hash at the breakpoint,
    # and no prior write exists at any earlier block -> no hit.
    blocks2 = [tok("system", 100), tok("message", 6, {"type": "ephemeral"})]
    second = cache.process(blocks2, [1], workspace="t")
    assert second.cache_read_input_tokens == 0  # the trap
    assert second.cache_creation_input_tokens == 106  # full rewrite every time


def test_5m_ttl_expiry() -> None:
    clock = FakeClock()
    cache = PromptCache(clock=clock)
    blocks = [tok("system", 50, {"type": "ephemeral"})]
    cache.process(blocks, [0], workspace="t")

    clock.tick(TTL_5M + 1)  # past the 5-minute lifetime
    second = cache.process(blocks, [0], workspace="t")
    assert second.cache_read_input_tokens == 0  # expired -> miss
    assert second.cache_creation_input_tokens == 50  # rewritten


def test_1h_ttl_survives_past_5m() -> None:
    clock = FakeClock()
    cache = PromptCache(clock=clock)
    blocks = [tok("system", 50, {"type": "ephemeral", "ttl": "1h"})]
    cache.process(blocks, [0], workspace="t")

    clock.tick(TTL_5M + 60)  # beyond 5m, well within 1h
    second = cache.process(blocks, [0], workspace="t")
    assert second.cache_read_input_tokens == 50  # still alive
    assert second.write_1h_tokens == 0  # not rewritten


def test_read_refreshes_ttl() -> None:
    clock = FakeClock()
    cache = PromptCache(clock=clock)
    blocks = [tok("system", 50, {"type": "ephemeral"})]
    cache.process(blocks, [0], workspace="t")  # expiry at 300

    clock.tick(250)  # within 5m
    assert cache.process(blocks, [0], workspace="t").hit  # refresh -> expiry now 550

    clock.tick(150)  # now 400; without refresh it would have expired at 300
    assert cache.process(blocks, [0], workspace="t").hit  # still alive thanks to refresh


def test_workspace_isolation() -> None:
    cache = PromptCache(clock=FakeClock())
    blocks = [tok("system", 40, {"type": "ephemeral"})]
    cache.process(blocks, [0], workspace="tenant-a")

    other = cache.process(blocks, [0], workspace="tenant-b")
    assert other.cache_read_input_tokens == 0  # isolated, no cross-tenant hit
    assert other.cache_creation_input_tokens == 40


def test_lookback_window_and_second_breakpoint() -> None:
    def seeded() -> tuple[PromptCache, list[Block]]:
        """A fresh cache whose only entry was written at index 9."""
        c = PromptCache(clock=FakeClock())
        short = [tok("message", 2) for _ in range(10)]
        c.process(short, [9], workspace="t")
        return c, short

    # 35 blocks whose first 10 are identical to the seeded prefix, so hash[9] matches.
    long_blocks = [tok("message", 2) for _ in range(35)]

    # Breakpoint only at 34: index 9 is outside the 20-block window (34..15) -> miss.
    c1, _ = seeded()
    miss = c1.process(long_blocks, [34], workspace="t")
    assert miss.cache_read_input_tokens == 0

    # A second breakpoint at 15 opens a lookback window (15..-4) that reaches 9 -> hit.
    c2, _ = seeded()
    hit = c2.process(long_blocks, [15, 34], workspace="t")
    assert hit.cache_read_input_tokens == 20  # 10 blocks * 2 tokens cached at index 9


def test_cost_multipliers() -> None:
    usage = Usage(
        cache_read_input_tokens=1000,
        cache_creation_input_tokens=2000,
        input_tokens=1000,
        write_5m_tokens=1000,
        write_1h_tokens=1000,
    )
    # base $1 / MTok: 1000*0.1 + 1000*1.25 + 1000*2 + 1000*1 = 4350 -> /1e6
    assert cost(usage, base_per_mtok=1.0) == pytest.approx(0.00435)


def test_total_input_accounting() -> None:
    cache = PromptCache(clock=FakeClock())
    blocks = [tok("system", 100, {"type": "ephemeral"}), tok("message", 30)]
    u = cache.process(blocks, [0], workspace="t")
    assert u.total_input == 130  # read/creation region + uncached suffix
