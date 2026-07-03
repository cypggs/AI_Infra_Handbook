import time

from openai_mini.limiter import TokenBucket


def test_token_bucket_allows_initial_burst():
    bucket = TokenBucket(rate=10, capacity=3)
    assert bucket.allow()
    assert bucket.allow()
    assert bucket.allow()
    assert not bucket.allow()


def test_token_bucket_refills():
    bucket = TokenBucket(rate=10, capacity=1)
    assert bucket.allow()
    assert not bucket.allow()
    time.sleep(0.15)
    assert bucket.allow()
