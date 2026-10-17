import pytest

from feature_store_mini.entity import Entity
from feature_store_mini.offline import OfflineFeatureTable
from feature_store_mini.online import OnlineFeatureStore


@pytest.fixture
def clock():
    now = [1000]
    return now, lambda: now[0]


def test_set_get_roundtrip(clock):
    _, c = clock
    store = OnlineFeatureStore(clock=c)
    store.set("u1", {"f": 1.0}, event_timestamp=100)
    assert store.get("u1") == {"f": 1.0}


def test_latest_write_wins(clock):
    _, c = clock
    store = OnlineFeatureStore(clock=c)
    store.set("u1", {"f": 1.0}, event_timestamp=100)
    store.set("u1", {"f": 2.0}, event_timestamp=200)
    assert store.get("u1") == {"f": 2.0}


def test_out_of_order_write_ignored(clock):
    _, c = clock
    store = OnlineFeatureStore(clock=c)
    store.set("u1", {"f": 2.0}, event_timestamp=200)
    store.set("u1", {"f": 1.0}, event_timestamp=100)
    assert store.get("u1") == {"f": 2.0}


def test_unknown_entity_returns_none(clock):
    _, c = clock
    store = OnlineFeatureStore(clock=c)
    assert store.get("nobody") is None


def test_ttl_expiry(clock):
    now, c = clock
    store = OnlineFeatureStore(ttl_seconds=60, clock=c)
    store.set("u1", {"f": 1.0}, event_timestamp=1000)
    now[0] = 1060
    assert store.get("u1") == {"f": 1.0}
    now[0] = 1061
    assert store.get("u1") is None


def test_ttl_disabled_by_default(clock):
    now, c = clock
    store = OnlineFeatureStore(clock=c)
    store.set("u1", {"f": 1.0}, event_timestamp=0)
    now[0] = 10**9
    assert store.get("u1") == {"f": 1.0}


def test_as_of_query_time(clock):
    """The online store keeps only the newest snapshot: a query time
    earlier than the snapshot must not see future values."""
    _, c = clock
    store = OnlineFeatureStore(clock=c)
    store.set("u1", {"f": 1.0}, event_timestamp=100)
    store.set("u1", {"f": 2.0}, event_timestamp=200)
    assert store.get("u1", as_of=250) == {"f": 2.0}
    assert store.get("u1", as_of=150) is None  # snapshot is from the future
    assert store.get("u1", as_of=50) is None


def test_feature_subset_projection(clock):
    _, c = clock
    store = OnlineFeatureStore(clock=c)
    store.set("u1", {"a": 1.0, "b": 2.0}, event_timestamp=100)
    assert store.get("u1", feature_names=["a"]) == {"a": 1.0}


def test_sync_from_offline(clock):
    _, c = clock
    table = OfflineFeatureTable("t", Entity("user", "user_id"), ["f"])
    table.ingest("u1", 100, {"f": 1.0})
    table.ingest("u1", 300, {"f": 3.0})
    table.ingest("u2", 200, {"f": 2.0})
    store = OnlineFeatureStore(clock=c)
    synced = store.sync_from_offline(table, as_of=300)
    assert synced == 2
    assert store.get("u1") == {"f": 3.0}  # latest snapshot, not the first
    assert store.get("u2") == {"f": 2.0}
    assert len(store) == 2


def test_sync_respects_ttl(clock):
    now, c = clock
    now[0] = 100
    table = OfflineFeatureTable("t", Entity("user", "user_id"), ["f"])
    table.ingest("u1", 100, {"f": 1.0})
    store = OnlineFeatureStore(ttl_seconds=500, clock=c)
    store.sync_from_offline(table, as_of=100)
    assert store.get("u1") == {"f": 1.0}
    now[0] = 601
    assert store.get("u1") is None
