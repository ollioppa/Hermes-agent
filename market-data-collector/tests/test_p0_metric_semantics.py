"""P0 contracts: unit-safe liquidations, held funding, and held briefing score."""

import json
from datetime import timedelta
from unittest.mock import patch

import pandas as pd

from src.clients import coinalyze
from src.config.settings import DB_COLUMNS
from src.scripts import market_briefing_snapshot as snapshot
from src.services import backfill


DAY = "2026-07-10"


def _daily_source_data(value=100.0):
    return {DAY: value}


def _db_row_by_column(rows):
    return dict(zip(DB_COLUMNS, rows[1]))


def test_liquidation_history_requests_explicit_usd_conversion():
    payload = [{"symbol": "BTCUSDT_PERP.A", "history": [{"t": coinalyze._to_unix(DAY), "l": 1, "s": 2}]}]

    with patch.object(coinalyze, "_get_with_retry", return_value=payload) as request:
        coinalyze.fetch_liquidations(DAY, DAY)

    assert request.call_args.kwargs["params"]["convert_to_usd"] == "true"


def test_db_builder_holds_funding_and_versions_complete_usd_liquidations():
    close_data = _daily_source_data()
    liq_data = {DAY: {"long": 0.0, "short": 2.0, "total": 2.0}}

    with (
        patch.object(backfill, "fetch_btcusdt_close", return_value=close_data),
        patch.object(backfill, "fetch_btc_close", return_value=close_data),
        patch.object(backfill, "_fetch_mstr_close", return_value=close_data),
        patch.object(backfill, "fetch_fear_greed", return_value=close_data),
        patch.object(backfill, "fetch_mvrv", return_value=close_data),
        patch.object(backfill, "fetch_open_interest_provenance", return_value={
            DAY: {"value": 100.0, "coverage_pct": 100.0}
        }),
        patch.object(backfill, "fetch_liquidations", return_value=liq_data),
        patch.object(backfill, "fetch_etf_inflows", return_value={}),
        patch.object(backfill, "compute_all", side_effect=lambda frame: frame),
        patch.object(backfill.time, "sleep"),
    ):
        row = _db_row_by_column(backfill._build_db_rows("2026-07-12T06:00:00+00:00", end_date=DAY))

    assert row["funding_daily_pct"] == ""
    status = json.loads(row["source_status_json"])
    assert status["funding"] == "held_no_daily_contract"
    assert status["liq"] == "ok_usd_v2"
    assert [row[c] for c in ("liq_daily_long_usd", "liq_daily_short_usd", "liq_daily_total_usd")] == [0.0, 2.0, 2.0]


def test_snapshot_reader_requests_unformatted_numbers(monkeypatch):
    sheet = object()
    seen = {}

    monkeypatch.setattr(snapshot, "get_sheet", lambda _: sheet)
    monkeypatch.setattr(
        snapshot,
        "read_all_values",
        lambda actual_sheet, *, unformatted: seen.update(sheet=actual_sheet, unformatted=unformatted)
        or [["date", "btc_binance_close"], [DAY, 64073.99]],
    )

    frame = snapshot.sheet_to_df("DB")

    assert seen == {"sheet": sheet, "unformatted": True}
    assert frame["btc_binance_close"].iloc[0] == 64073.99


def test_thermometer_snapshot_bounds_repeated_scoring_to_required_history(monkeypatch):
    as_of = pd.Timestamp("2026-08-04")
    dates = pd.date_range(end=as_of, periods=400, freq="D")
    db = pd.DataFrame({"date": dates, "source_status_json": ["{}"] * len(dates)})
    seen_ranges = []

    def fake_daily(records, day):
        record_dates = pd.to_datetime(records["date"])
        seen_ranges.append((record_dates.min().date(), record_dates.max().date()))
        return {
            "score_schema_version": "composite_thermometer_v1",
            "status": "unavailable",
            "score": None,
            "bucket": None,
        }

    monkeypatch.setattr(snapshot, "build_daily_thermometer", fake_daily)
    monkeypatch.setattr(snapshot, "build_weekly_history", lambda *_: [])
    monkeypatch.setattr(snapshot, "_with_display", lambda value: value)

    snapshot.build_thermometer_snapshot(db)

    current_monday = as_of.date() - timedelta(days=as_of.weekday())
    required_start = current_monday - timedelta(days=42 + 180)
    assert seen_ranges
    assert all(start == required_start and end == as_of.date() for start, end in seen_ranges)


def _snapshot_payload(monkeypatch, capsys, liq_status="ok"):
    db = pd.DataFrame([
        {
            "date": pd.Timestamp(DAY),
            "btc_binance_close": 100000,
            "btc_coinbase_close": 100100,
            "mstr_close": 200,
            "fear_greed": 25,
            "mvrv": 1.2,
            "perp_oi_usd": 20_000_000_000,
            "funding_daily_pct": 0.2,
            "liq_daily_total_usd": 500_000,
            "source_status_json": json.dumps({"funding": "held_no_daily_contract", "liq": liq_status}),
        }
    ])
    market = pd.DataFrame([{"date": pd.Timestamp(DAY), "BTC": 100000}])
    monkeypatch.setattr(snapshot, "sheet_to_df", lambda name: db if name == "DB" else market)

    snapshot.main()
    return json.loads(capsys.readouterr().out)


def test_snapshot_emits_the_versioned_thermometer_and_omits_held_funding(monkeypatch, capsys):
    expected_score = {
        "score_schema_version": "composite_thermometer_v1",
        "status": "partial",
        "score": None,
        "bucket": None,
        "funding_diagnostic": {
            "id": "funding",
            "status": "held",
            "reason_code": "held_no_documented_settlement_aggregation",
            "points": None,
        },
        "weekly_history": [],
    }
    monkeypatch.setattr(snapshot, "build_thermometer_snapshot", lambda _: expected_score, raising=False)

    payload = _snapshot_payload(monkeypatch, capsys)

    assert payload["score"] == expected_score
    assert "funding_daily_pct" not in payload["indicators"]


def test_snapshot_rejects_legacy_liquidation_rows(monkeypatch, capsys):
    payload = _snapshot_payload(monkeypatch, capsys, liq_status="ok")

    assert "liq_daily_total_usd" not in payload["indicators"]


def test_snapshot_allows_v2_usd_liquidations(monkeypatch, capsys):
    payload = _snapshot_payload(monkeypatch, capsys, liq_status="ok_usd_v2")

    assert payload["indicators"]["liq_daily_total_usd"]["current"] == 500_000


def test_snapshot_allows_kept_prior_validated_liquidations(monkeypatch, capsys):
    payload = _snapshot_payload(monkeypatch, capsys, liq_status="kept_prior")

    assert payload["indicators"]["liq_daily_total_usd"]["current"] == 500_000
