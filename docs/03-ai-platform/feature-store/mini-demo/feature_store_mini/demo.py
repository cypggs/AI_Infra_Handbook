"""End-to-end mini demo: events -> offline PIT training set -> online
serving -> skew detection.  Deterministic: fixed timestamps and an
injected fake clock, no wall-clock dependence.
"""

from __future__ import annotations

from .entity import Entity
from .offline import QUERY_TS, OfflineFeatureTable
from .online import OnlineFeatureStore
from .skew import detect_skew, feature_distribution, psi

DAY = 86_400
T0 = 1_700_000_000  # fixed logical epoch, fully deterministic
USERS = [f"u{i}" for i in range(1, 6)]


def build_events() -> list[dict]:
    """Deterministic pseudo event stream: user daily spend."""
    events = []
    for d in range(10):  # 10 days
        for i, user in enumerate(USERS):
            amount = float((i * 7 + d * 13) % 50 + 1)
            events.append({"user_id": user, QUERY_TS: T0 + d * DAY, "amount": amount})
    return events


def offline_window_spend(events: list[dict], user: str, ts: int, window_days: int = 7) -> float:
    """Batch recomputation of `spend_sum_7d` straight from the raw log."""
    lo = ts - (window_days - 1) * DAY
    return sum(
        e["amount"]
        for e in events
        if e["user_id"] == user and lo <= e[QUERY_TS] <= ts
    )


def scenario_events_to_offline(events: list[dict]) -> OfflineFeatureTable:
    """Feature pipeline: windowed aggregation written into the offline table."""
    user = Entity("user", "user_id", "application user")
    table = OfflineFeatureTable("user_spend_7d", user, ["spend_sum_7d"])
    for e in events:
        ts = e[QUERY_TS]
        table.ingest(
            e["user_id"],
            ts,
            {"spend_sum_7d": offline_window_spend(events, e["user_id"], ts)},
        )
    return table


def scenario_pit_training_set(table: OfflineFeatureTable, events: list[dict]) -> dict:
    """Labels observed on day 10; features must come from <= label time."""
    query_ts = T0 + 9 * DAY
    query_rows = [{table.entity.join_key: u, QUERY_TS: query_ts, "label": 1.0} for u in USERS]
    training = table.point_in_time_join(query_rows)
    no_leakage = all(
        table.as_of(r[table.entity.join_key], r[QUERY_TS]) is not None
        and table.all_timestamps(r[table.entity.join_key])[-1] is not None
        for r in training
    )
    # stronger check: the value served equals the batch recomputation
    no_leakage = all(
        abs(r["spend_sum_7d"] - offline_window_spend(events, r["user_id"], r[QUERY_TS])) < 1e-9
        for r in training
    )
    return {"training_rows": len(training), "no_leakage": no_leakage}


def scenario_online_serving(table: OfflineFeatureTable) -> dict:
    """Materialize snapshots to the online store and demonstrate TTL."""
    now = [T0 + 10 * DAY]
    clock = lambda: now[0]  # noqa: E731 - tiny injectable fake clock
    store = OnlineFeatureStore(ttl_seconds=3 * DAY, clock=clock)
    synced = store.sync_from_offline(table, as_of=T0 + 9 * DAY)
    served = {u: store.get(u)["spend_sum_7d"] for u in USERS}
    now[0] = T0 + 10 * DAY  # +1 day: still fresh
    fresh = store.get(USERS[0]) is not None
    now[0] = T0 + 13 * DAY  # +4 days: TTL (3d) expired
    expired = store.get(USERS[0]) is None
    return {"synced": synced, "served_users": len(served), "fresh_after_1d": fresh, "expired_after_4d": expired}


def scenario_skew_aligned(table: OfflineFeatureTable, events: list[dict]) -> dict:
    """Offline recomputation vs online snapshot of the same logical feature."""
    ts = T0 + 9 * DAY
    pairs = [
        (offline_window_spend(events, u, ts), table.as_of(u, ts)["spend_sum_7d"])
        for u in USERS
    ]
    report = detect_skew(pairs, abs_tol=1e-9)
    return {"skewed": report["skewed"], "compared": report["compared"]}


def scenario_skew_window_bug(events: list[dict]) -> dict:
    """Online path uses a 3-day window while training used 7 days -> skew."""
    ts = T0 + 9 * DAY
    offline_vals = [offline_window_spend(events, u, ts, window_days=7) for u in USERS]
    buggy_vals = [offline_window_spend(events, u, ts, window_days=3) for u in USERS]
    report = detect_skew(list(zip(offline_vals, buggy_vals)), abs_tol=1e-9)
    dist_offline = feature_distribution(offline_vals)
    dist_buggy = feature_distribution(buggy_vals)
    drift = psi(offline_vals, buggy_vals, bins=5)
    return {
        "skewed": report["skewed"],
        "mismatched": report["mismatched"],
        "psi": round(drift, 4),
        "offline_mean": round(dist_offline["mean"], 2),
        "serving_mean": round(dist_buggy["mean"], 2),
    }


def scenario_late_arriving_event(table: OfflineFeatureTable, events: list[dict]) -> dict:
    """A late event triggers a backfill that retro-corrects history.

    The offline table is append-only, so correction means recomputing
    every downstream window row (same timestamp, newer version).
    """
    user = USERS[0]
    late_ts = T0 + 5 * DAY  # happened on day 5, arrives on day 10
    events.append({"user_id": user, QUERY_TS: late_ts, "amount": 999.0})
    rows_before = table.row_count(user)
    for d in range(5, 10):  # backfill: days 5..9 all see the late event
        ts = T0 + d * DAY
        table.ingest(user, ts, {"spend_sum_7d": offline_window_spend(events, user, ts)})
    corrected = table.as_of(user, T0 + 6 * DAY)["spend_sum_7d"]
    before_fix = offline_window_spend(events[:-1], user, T0 + 6 * DAY)
    return {
        "corrected": corrected,
        "delta": round(corrected - before_fix, 2),
        "retro_corrected": corrected > before_fix,
        "rows_added": table.row_count(user) - rows_before,
    }


def run_demo() -> dict:
    events = build_events()
    table = scenario_events_to_offline(events)
    pit = scenario_pit_training_set(table, events)
    online = scenario_online_serving(table)
    aligned = scenario_skew_aligned(table, events)
    buggy = scenario_skew_window_bug(events)
    late = scenario_late_arriving_event(table, events)

    summary = {
        "offline_rows": table.row_count(),
        "pit_training_rows": pit["training_rows"],
        "pit_no_leakage": pit["no_leakage"],
        "online_synced": online["synced"],
        "online_ttl_works": online["expired_after_4d"] and online["fresh_after_1d"],
        "aligned_skewed": aligned["skewed"],
        "buggy_skew": buggy,
        "late_event_delta": late["delta"],
        "retro_corrected": late["retro_corrected"],
    }
    print("Demo result:", summary)
    return summary


if __name__ == "__main__":
    run_demo()
