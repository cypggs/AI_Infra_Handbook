import pytest

from feature_store_mini.entity import Entity
from feature_store_mini.offline import QUERY_TS, OfflineFeatureTable


@pytest.fixture
def table():
    return OfflineFeatureTable("t", Entity("user", "user_id"), ["f1", "f2"])


def test_ingest_and_as_of_basic(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 2.0})
    assert table.as_of("u1", 100) == {"f1": 1.0, "f2": 2.0}
    assert table.as_of("u1", 101) == {"f1": 1.0, "f2": 2.0}
    assert table.as_of("u1", 99) is None  # before any event


def test_as_of_picks_latest_not_future(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 1.0})
    table.ingest("u1", 200, {"f1": 2.0, "f2": 2.0})
    table.ingest("u1", 300, {"f1": 3.0, "f2": 3.0})
    assert table.as_of("u1", 250) == {"f1": 2.0, "f2": 2.0}


def test_no_future_leakage(table):
    table.ingest("u1", 200, {"f1": 2.0, "f2": 2.0})
    assert table.as_of("u1", 100) is None


def test_unsorted_ingestion_stays_sorted(table):
    for ts in [300, 100, 200]:
        table.ingest("u1", ts, {"f1": float(ts), "f2": 0.0})
    assert table.all_timestamps("u1") == [100, 200, 300]


def test_ingest_missing_feature_rejected(table):
    with pytest.raises(KeyError):
        table.ingest("u1", 100, {"f1": 1.0})


def test_ingest_unknown_feature_rejected(table):
    with pytest.raises(KeyError):
        table.ingest("u1", 100, {"f1": 1.0, "f2": 0.0, "f3": 9.0})


def test_unknown_entity_returns_none(table):
    assert table.as_of("nobody", 999) is None


def test_max_age_filters_stale_rows(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 1.0})
    assert table.as_of("u1", 160, max_age=60) == {"f1": 1.0, "f2": 1.0}
    assert table.as_of("u1", 161, max_age=60) is None


def test_tie_timestamp_latest_insert_wins(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 1.0})
    table.ingest("u1", 100, {"f1": 5.0, "f2": 5.0})
    assert table.as_of("u1", 100) == {"f1": 5.0, "f2": 5.0}


def test_pit_join_assembles_training_rows(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 10.0})
    table.ingest("u2", 150, {"f1": 2.0, "f2": 20.0})
    rows = table.point_in_time_join(
        [
            {"user_id": "u1", QUERY_TS: 120, "label": 0.0},
            {"user_id": "u2", QUERY_TS: 120, "label": 1.0},
            {"user_id": "u1", QUERY_TS: 200, "label": 0.0},
        ]
    )
    assert rows[0]["f1"] == 1.0 and rows[0]["label"] == 0.0
    assert rows[1]["f1"] is None  # u2 has no row <= 120
    assert rows[1]["label"] == 1.0
    assert rows[2]["f1"] == 1.0  # still the day-100 value: no leakage


def test_pit_join_passes_through_extra_columns(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 2.0})
    rows = table.point_in_time_join([{"user_id": "u1", QUERY_TS: 200, "extra": "x"}])
    assert rows[0]["extra"] == "x"


def test_ingest_many_from_raw_records(table):
    n = table.ingest_many(
        [
            {"user_id": "u1", QUERY_TS: 100, "f1": 1.0, "f2": 2.0},
            {"user_id": "u2", QUERY_TS: 200, "f1": 3.0, "f2": 4.0},
        ]
    )
    assert n == 2
    assert table.row_count() == 2


def test_row_count_per_entity(table):
    table.ingest("u1", 100, {"f1": 1.0, "f2": 2.0})
    table.ingest("u1", 200, {"f1": 1.0, "f2": 2.0})
    table.ingest("u2", 150, {"f1": 1.0, "f2": 2.0})
    assert table.row_count("u1") == 2
    assert table.row_count() == 3


def test_latest_timestamp(table):
    assert table.latest_timestamp("u1") is None
    table.ingest("u1", 100, {"f1": 1.0, "f2": 2.0})
    table.ingest("u1", 300, {"f1": 1.0, "f2": 2.0})
    table.ingest("u1", 200, {"f1": 1.0, "f2": 2.0})
    assert table.latest_timestamp("u1") == 300


def test_empty_feature_names_rejected():
    with pytest.raises(ValueError):
        OfflineFeatureTable("t", Entity("user", "user_id"), [])
