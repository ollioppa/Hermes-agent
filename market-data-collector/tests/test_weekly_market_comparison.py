import pandas as pd

from src.scripts.market_briefing_snapshot import weekly_comparison, weekly_metric


def frame(rows):
    return pd.DataFrame(rows, columns=["date", "value"])


def test_level_uses_last_valid_point_in_previous_calendar_week_not_previous_row():
    data = frame([
        ("2026-07-11", 110),
        ("2026-07-10", 109),
        ("2026-07-04", 100),
        ("2026-07-03", 99),
    ])
    data["date"] = pd.to_datetime(data["date"])

    result = weekly_comparison(data, ["value"], "level")

    assert result["reference_kind"] == "weekly_last"
    assert result["reference"] == 100
    assert result["reference_date"] == pd.Timestamp("2026-07-04")
    assert result["delta_abs"] == 10


def test_level_does_not_reach_back_beyond_immediately_previous_week():
    data = frame([("2026-07-11", 110), ("2026-06-27", 100)])
    data["date"] = pd.to_datetime(data["date"])

    result = weekly_comparison(data, ["value"], "level")

    assert result["reference_available"] is False
    assert result["reference"] is None


def test_flow_is_held_when_calendar_coverage_policy_is_unknown():
    data = frame([
        ("2026-07-06", 10), ("2026-07-07", 20), ("2026-07-08", 30),
        ("2026-06-29", 1), ("2026-06-30", 2), ("2026-07-01", 3),
    ])
    data["date"] = pd.to_datetime(data["date"])

    result = weekly_comparison(data, ["value"], "flow")

    assert result["reference_kind"] == "weekly_wtd_sum"
    assert result["reference_available"] is False
    assert result["current"] is None
    assert result["reference"] is None
    assert result["delta_abs"] is None
    assert result["delta_pct"] is None
    assert result["coverage_status"] == "calendar_unknown"
    assert result["observed_current_offsets"] == [0, 1, 2]
    assert result["observed_reference_offsets"] == [0, 1, 2]


def test_weekly_metric_exports_true_four_week_level_comparison():
    data = frame([
        ("2026-07-21", 120),
        ("2026-07-19", 110),
        ("2026-06-28", 100),
        ("2026-06-27", 99),
    ])
    data["date"] = pd.to_datetime(data["date"])

    result = weekly_metric(data, ["value"], "level")

    four_week = result["four_week_comparison"]
    assert four_week["reference_kind"] == "four_week_last"
    assert four_week["reference"] == 100
    assert four_week["reference_date"] == pd.Timestamp("2026-06-28")
    assert four_week["delta_abs"] == 20
    assert four_week["delta_pct"] == 20


def test_four_week_comparison_does_not_substitute_a_stale_week():
    data = frame([
        ("2026-07-21", 120),
        ("2026-06-21", 100),
    ])
    data["date"] = pd.to_datetime(data["date"])

    result = weekly_metric(data, ["value"], "level")["four_week_comparison"]

    assert result["reference_available"] is False
    assert result["reference"] is None


def test_flow_rejects_missing_matching_reference_day():
    data = frame([
        ("2026-07-06", 10), ("2026-07-07", 20),
        ("2026-06-29", 1),
    ])
    data["date"] = pd.to_datetime(data["date"])

    assert weekly_comparison(data, ["value"], "flow")["reference_available"] is False



def test_daily_readers_order_by_date_without_mutating_input():
    from src.scripts.market_briefing_snapshot import delta, first_valid
    # Historical insert placed above newest date, plus an old tail row.
    data = frame([("2026-07-10", 20), ("2026-07-11", 30), ("2026-07-09", 10)])
    original = data.copy(deep=True)
    result = delta(data, ["value"])
    assert (result["current"], result["previous"]) == (30, 20)
    assert (result["current_date"], result["previous_date"]) == (
        pd.Timestamp("2026-07-11"), pd.Timestamp("2026-07-10"))
    assert first_valid(data, ["value"]) == (30, pd.Timestamp("2026-07-11"))
    pd.testing.assert_frame_equal(data, original)
    nominal = data.sort_values("date", ascending=False)
    assert delta(nominal, ["value"]) == result


def test_daily_readers_skip_undated_and_sparse_rows_and_keep_first_date_tie():
    from src.scripts.market_briefing_snapshot import delta, first_valid
    data = frame([(None, 999), ("bad", 888), ("2026-07-12", ""),
                  ("2026-07-11", 30), ("2026-07-11", 300), ("2026-07-10", 20)])
    result = delta(data, ["missing", "value"])
    assert (result["current"], result["previous"]) == (30, 20)
    assert first_valid(data, ["value"]) == (30, pd.Timestamp("2026-07-11"))
    for unavailable in (frame([(None, 1)]), pd.DataFrame({"value": [1]}), frame([])):
        assert delta(unavailable, ["value"])["current"] is None
        assert first_valid(unavailable, ["value"]) == (None, None)
    assert delta(frame([("2026-07-11", 30), ("2026-07-11", 300)]), ["value"])["previous"] is None


def test_snapshot_latest_metadata_and_metrics_ignore_historical_insertion(monkeypatch, capsys):
    import json
    from src.scripts import market_briefing_snapshot as module
    db = pd.DataFrame([
        {"date": day, "btc_binance_close": value, "flex_signal": value,
         "source_status_json": json.dumps({"test_day": day})}
        for day, value in [("2026-07-10", 20), ("2026-07-11", 30), ("2026-07-09", 10)]
    ])
    market = pd.DataFrame({"date": ["2026-07-10", "2026-07-11", "2026-07-09"], "BTC": [20, 30, 10]})
    tables = {"DB": db, "MARKET_DATA": market, "MACRO_DATA": pd.DataFrame(columns=["date"])}
    monkeypatch.setattr(module, "get_sheet", lambda name: name)
    monkeypatch.setattr(module, "read_all_values", lambda name, **kwargs: [list(tables[name].columns), *tables[name].values.tolist()])
    module.main()
    unsorted = json.loads(capsys.readouterr().out)
    assert unsorted["db_date"] == unsorted["market_date"] == "2026-07-11"
    assert unsorted["source_status"] == {"test_day": "2026-07-11"}
    assert unsorted["indicators"]["flex_signal"]["current"] == 30
    assert unsorted["indicators"]["btc"]["current"] == 30
    assert unsorted["indicators"]["btc"]["previous"] == 20
    assert unsorted["market_data"]["BTC"]["current"] == 30
    for name in ("DB", "MARKET_DATA"):
        tables[name] = tables[name].sort_values("date", ascending=False)
    module.main()
    nominal = json.loads(capsys.readouterr().out)
    # The Weekly producer attaches wallclock time; all business output is identical.
    for result in (nominal, unsorted):
        result["score"].pop("producer_completed_at", None)
    assert nominal == unsorted
    pd.testing.assert_frame_equal(db, pd.DataFrame([
        {"date": day, "btc_binance_close": value, "flex_signal": value,
         "source_status_json": json.dumps({"test_day": day})}
        for day, value in [("2026-07-10", 20), ("2026-07-11", 30), ("2026-07-09", 10)]
    ]))



def test_snapshot_without_dated_db_fails_closed(monkeypatch):
    import pytest
    from src.scripts import market_briefing_snapshot as module
    monkeypatch.setattr(module, "sheet_to_df", lambda name: pd.DataFrame({"date": [pd.NaT]}))
    with pytest.raises(ValueError, match="DB contains no valid dated rows"):
        module.main()


def test_daily_freshness_anchors_and_opt_in_cli(monkeypatch, capsys):
    import copy
    import json
    import pytest
    from datetime import datetime, timezone
    from src.scripts import market_briefing_snapshot as module

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            # UTC is still the previous day; Berlin has crossed midnight.
            return datetime(2026, 11, 23, 23, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(module, "datetime", Clock)
    day = "2026-11-23"
    fresh = {"db_date": day, "score": {"as_of_date": day, "status": "complete"},
             "indicators": {"btc": {"current_date": day}},
             "market_data": {"BTC": {"current_date": day}}}
    module.validate_daily_freshness(fresh, day)
    for path in (("db_date",), ("score", "as_of_date"),
                 ("indicators", "btc", "current_date"), ("market_data", "BTC", "current_date")):
        for bad in (None, "", "2026-11-22", "2026-11-24", "20261123", "2026-11-23T00:00:00", 20261123):
            value = copy.deepcopy(fresh)
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = bad
            with pytest.raises(ValueError, match="daily freshness"):
                module.validate_daily_freshness(value, day)
    tables = {
        "DB": pd.DataFrame({"date": pd.to_datetime([day]), "btc_binance_close": [12345]}),
        "MARKET_DATA": pd.DataFrame({"date": pd.to_datetime([day]), "BTC": [12345]}),
        "MACRO_DATA": pd.DataFrame(columns=["date"]),
    }
    monkeypatch.setattr(module, "sheet_to_df", lambda name: tables[name].copy())
    monkeypatch.setattr(module, "build_thermometer_snapshot", lambda db: dict(fresh["score"]))
    monkeypatch.setattr(module, "build_sector_snapshot", lambda *args: {})
    module.main(["--require-current-daily"])
    assert json.loads(capsys.readouterr().out)["market_data"]["BTC"]["current_date"] == day
    tables["MARKET_DATA"]["date"] = pd.to_datetime(["2026-11-22"])
    with pytest.raises(SystemExit) as exc:
        module.main(["--require-current-daily"])
    assert exc.value.code != 0
    output = capsys.readouterr()
    assert not output.out and "market_data.BTC.current_date" in output.err
    module.main([])  # Existing historical/default behavior remains opt-out.
    assert json.loads(capsys.readouterr().out)["market_data"]["BTC"]["current_date"] == "2026-11-22"
    for flags in (["--sectors-only"], ["--as-of", day]):
        with pytest.raises(SystemExit):
            module.main(["--require-current-daily", *flags])
