import pytest

from llm_gateway_mini.rate_limiter import TokenBucket


def test_allow_within_burst():
    now = [0.0]
    bucket = TokenBucket(rate_per_second=1.0, capacity=3, clock=lambda: now[0])
    assert bucket.allow("k") is True
    assert bucket.allow("k") is True
    assert bucket.allow("k") is True
    assert bucket.allow("k") is False

    now[0] = 2.0
    # 2 tokens refilled, 2 consumed -> 0 left
    assert bucket.allow("k") is True
    assert bucket.allow("k") is True
    assert bucket.allow("k") is False


def test_separate_keys_do_not_share_tokens():
    bucket = TokenBucket(rate_per_second=10.0, capacity=1)
    assert bucket.allow("a") is True
    assert bucket.allow("b") is True
    assert bucket.allow("a") is False


def test_from_config():
    from llm_gateway_mini.config import RateLimitConfig

    bucket = TokenBucket.from_config(RateLimitConfig(requests_per_minute=120, burst=20))
    assert bucket.rate_per_second == 2.0
    assert bucket.capacity == 20.0
