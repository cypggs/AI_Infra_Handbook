from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict

from .config import RateLimitConfig


@dataclass
class TokenBucket:
    """Thread-safe token bucket rate limiter keyed by arbitrary strings."""

    rate_per_second: float = 1.0
    capacity: float = 10.0
    clock: Callable[[], float] = field(default_factory=lambda: time.monotonic)
    _tokens: Dict[str, float] = field(default_factory=dict)
    _last_update: Dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def from_config(cls, config: RateLimitConfig) -> "TokenBucket":
        return cls(
            rate_per_second=config.requests_per_minute / 60.0,
            capacity=float(config.burst),
        )

    def allow(self, key: str, tokens: float = 1.0) -> bool:
        with self._lock:
            now = self.clock()
            last = self._last_update.get(key, now)
            elapsed = now - last
            current = self._tokens.get(key, self.capacity)
            current = min(self.capacity, current + elapsed * self.rate_per_second)
            self._last_update[key] = now

            if current >= tokens:
                self._tokens[key] = current - tokens
                return True
            else:
                self._tokens[key] = current
                return False
