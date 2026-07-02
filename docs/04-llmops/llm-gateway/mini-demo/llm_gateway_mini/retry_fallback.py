from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class RetryPolicy:
    """Exponential-backoff retry policy."""

    max_retries: int = 2
    base_delay: float = 0.05
    max_delay: float = 1.0
    exponential: bool = True
    sleep: Callable[[float], None] = field(default_factory=lambda: time.sleep)

    def sleep_duration(self, attempt: int) -> float:
        if self.exponential:
            return min(self.max_delay, self.base_delay * (2 ** attempt))
        return self.base_delay

    def call(self, func: Callable, *args, **kwargs) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise
                self.sleep(self.sleep_duration(attempt))
        raise last_exc  # pragma: no cover


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    """Simple circuit breaker with closed/open/half-open states."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 0.5,
        clock: Callable[[], float] = None,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.clock = clock or time.monotonic
        self.failures = 0
        self.state = "closed"
        self.last_failure_time = 0.0
        self._lock = threading.Lock()

    def _reset(self) -> None:
        self.failures = 0
        self.state = "closed"

    def call(self, func: Callable, *args, **kwargs) -> Any:
        with self._lock:
            if self.state == "open":
                if self.clock() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "half-open"
                else:
                    raise CircuitBreakerOpen("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            with self._lock:
                if self.state == "half-open":
                    self._reset()
            return result
        except Exception as exc:
            with self._lock:
                self.failures += 1
                self.last_failure_time = self.clock()
                if self.failures >= self.failure_threshold:
                    self.state = "open"
            raise


class FallbackChain:
    """Try a list of candidates until one succeeds."""

    def __init__(
        self,
        candidates: List[Any],
        retry_policy: RetryPolicy,
        breakers: Optional[Dict[Any, CircuitBreaker]] = None,
    ):
        self.candidates = candidates
        self.retry_policy = retry_policy
        self.breakers = breakers or {}

    def execute(self, invoke: Callable[[Any], Any]) -> Tuple[Any, Any]:
        last_exc: Optional[Exception] = None
        for candidate in self.candidates:
            breaker = self.breakers.get(candidate)
            try:
                if breaker is not None:
                    result = breaker.call(self.retry_policy.call, invoke, candidate)
                else:
                    result = self.retry_policy.call(invoke, candidate)
                return candidate, result
            except Exception as exc:
                last_exc = exc
        raise last_exc or RuntimeError("No candidates available")
