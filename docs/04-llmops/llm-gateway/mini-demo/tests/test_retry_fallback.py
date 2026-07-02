import pytest

from llm_gateway_mini.retry_fallback import (
    CircuitBreaker,
    CircuitBreakerOpen,
    FallbackChain,
    RetryPolicy,
)


def test_retry_succeeds_eventually():
    sleeps = []

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("fail")
        return "ok"

    policy = RetryPolicy(max_retries=3, base_delay=0.01, sleep=lambda x: sleeps.append(x))
    assert policy.call(flaky) == "ok"
    assert len(attempts) == 3
    assert sleeps == [pytest.approx(0.01), pytest.approx(0.02)]


def test_retry_exhausted():
    policy = RetryPolicy(max_retries=2, base_delay=0.01, sleep=lambda x: None)

    with pytest.raises(RuntimeError, match="fail"):
        policy.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))


def test_circuit_breaker_trips_and_recovers():
    now = [0.0]
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0, clock=lambda: now[0])

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    assert cb.state == "closed"

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    assert cb.state == "open"

    with pytest.raises(CircuitBreakerOpen):
        cb.call(lambda: "ok")

    now[0] = 2.0
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state == "closed"


def test_fallback_chain_uses_first_working_candidate():
    def invoke(candidate):
        if candidate == "a":
            raise RuntimeError("a fails")
        return candidate.upper()

    chain = FallbackChain(["a", "b", "c"], RetryPolicy(max_retries=0))
    provider, result = chain.execute(invoke)
    assert provider == "b"
    assert result == "B"


def test_fallback_chain_all_fail():
    chain = FallbackChain(["a", "b"], RetryPolicy(max_retries=0))
    with pytest.raises(RuntimeError):
        chain.execute(lambda c: (_ for _ in ()).throw(RuntimeError("fail")))
