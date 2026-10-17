from feature_store_mini import demo


def test_demo_summary_keys():
    summary = demo.run_demo()
    for key in (
        "offline_rows",
        "pit_training_rows",
        "pit_no_leakage",
        "online_synced",
        "online_ttl_works",
        "aligned_skewed",
        "buggy_skew",
        "late_event_delta",
        "retro_corrected",
    ):
        assert key in summary


def test_pit_training_set_has_no_leakage():
    events = demo.build_events()
    table = demo.scenario_events_to_offline(events)
    result = demo.scenario_pit_training_set(table, events)
    assert result["training_rows"] == len(demo.USERS)
    assert result["no_leakage"] is True


def test_online_ttl_scenario():
    events = demo.build_events()
    table = demo.scenario_events_to_offline(events)
    result = demo.scenario_online_serving(table)
    assert result["synced"] == len(demo.USERS)
    assert result["served_users"] == len(demo.USERS)
    assert result["fresh_after_1d"] is True
    assert result["expired_after_4d"] is True


def test_aligned_paths_show_no_skew():
    events = demo.build_events()
    table = demo.scenario_events_to_offline(events)
    result = demo.scenario_skew_aligned(table, events)
    assert result["skewed"] is False
    assert result["compared"] == len(demo.USERS)


def test_window_bug_detected():
    result = demo.scenario_skew_window_bug(demo.build_events())
    assert result["skewed"] is True
    assert result["mismatched"] > 0
    assert result["psi"] > 0.25  # significant drift
    assert result["serving_mean"] != result["offline_mean"]


def test_late_event_retro_corrects_offline():
    events = demo.build_events()
    table = demo.scenario_events_to_offline(events)
    result = demo.scenario_late_arriving_event(table, events)
    assert result["retro_corrected"] is True
    assert result["delta"] == 999.0  # the late amount lands in the 7d window
    assert result["rows_added"] == 5  # backfill rewrote days 5..9
    assert table.row_count(demo.USERS[0]) == 15
