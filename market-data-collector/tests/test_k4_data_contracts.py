"""K4 open-data contracts: MA source visibility (OD-8), partial-window marking
(OD-14), non-trading-day no-forward-fill (OD-9) and the one-date-one-row
invariant without an active dedup job (OD-12).

Contract representation: OD-8/OD-14 markers are carried inside the already
persisted, already consumed ``source_status_json`` column (no new DB column,
no MARKET_DATA header change). Legacy rows without the keys stay fail-closed.
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd

from src.config.settings import DB_COLUMNS
from src.services import backfill
from src.services.google_sheets import upsert_rows
from src.services.indicators import compute_all


def _base_frame(dates, **overrides):
    n = len(dates)
    data = {
        "date": dates,
        "btc_binance_close": [100.0] * n,
        "btc_coinbase_close": [100.0] * n,
        "mstr_close": [10.0] * n,
        "fear_greed": [50.0] * n,
        "mvrv": [1.0] * n,
        "perp_oi_usd": [1.0] * n,
        "funding_daily_pct": [None] * n,
        "liq_daily_total_usd": [None] * n,
        "liq_daily_long_usd": [None] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data)


def _status(df, row=-1):
    return json.loads(df.iloc[row]["source_status_json"])


# ── (b) OD-14 partial-window marking ─────────────────────────────


def test_partial_rolling_window_is_emitted_but_marked():
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    out = compute_all(_base_frame(dates))
    row = out.iloc[-1]
    # emit-but-marked: value is present, but flagged so no consumer treats a
    # 3-observation "30d median" as a full window.
    assert pd.notna(row["mvrv_30d_median"])
    assert "mvrv_30d_median" in _status(out)["partial_windows"]


def test_full_rolling_window_is_not_marked_partial():
    dates = pd.date_range("2025-01-01", periods=35, freq="D")
    out = compute_all(_base_frame(dates))
    assert "mvrv_30d_median" not in _status(out)["partial_windows"]


def test_held_source_metric_is_not_reported_as_partial():
    # funding stays held (None) -> the rolling metric is NaN and must not be
    # flagged partial (partial is emit-but-marked, not missing).
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    out = compute_all(_base_frame(dates))
    assert "funding_7d_pct" not in _status(out)["partial_windows"]


# ── (a) OD-8 canonical Coinbase / visible Binance fallback ────────


def test_ma_reference_point_marks_coinbase_canonical():
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    out = compute_all(_base_frame(dates))
    assert _status(out)["btc_ma_source"] == "coinbase"


def test_ma_reference_point_marks_binance_fallback_when_coinbase_missing():
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    df = _base_frame(dates)
    df.loc[df.index[-1], "btc_coinbase_close"] = None
    out = compute_all(df)
    assert _status(out)["btc_ma_source"] == "binance_fallback"


def test_ma_reference_point_marks_missing_when_no_btc_price():
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    df = _base_frame(dates)
    df.loc[df.index[-1], "btc_coinbase_close"] = None
    df.loc[df.index[-1], "btc_binance_close"] = None
    out = compute_all(df)
    assert _status(out)["btc_ma_source"] == "missing"


# ── (c) OD-9 non-trading day: empty cell, no forward-fill ─────────


def test_non_trading_day_equity_cell_stays_empty_without_forward_fill():
    crypto = {"2026-07-10": 100.0, "2026-07-11": 101.0}
    mstr_only_friday = {"2026-07-10": 200.0}

    with (
        patch.object(backfill, "fetch_btcusdt_close", return_value=crypto),
        patch.object(backfill, "fetch_btc_close", return_value=crypto),
        patch.object(backfill, "_fetch_mstr_close", return_value=mstr_only_friday),
        patch.object(backfill, "fetch_fear_greed", return_value=crypto),
        patch.object(backfill, "fetch_mvrv", return_value=crypto),
        patch.object(
            backfill,
            "fetch_open_interest_provenance",
            return_value={day: {"value": value, "coverage_pct": 100.0} for day, value in crypto.items()},
        ),
        patch.object(backfill, "fetch_liquidations", return_value={}),
        patch.object(backfill, "fetch_etf_inflows", return_value={}),
        patch.object(backfill, "compute_all", side_effect=lambda frame: frame),
        patch.object(backfill.time, "sleep"),
    ):
        rows = backfill._build_db_rows("2026-07-12T06:00:00+00:00", end_date="2026-07-11")

    by_date = {r[0]: dict(zip(DB_COLUMNS, r)) for r in rows[1:]}
    assert by_date["2026-07-10"]["mstr_close"] == 200.0
    # Non-trading day: empty, never carried forward from the prior session.
    assert by_date["2026-07-11"]["mstr_close"] == ""
    assert json.loads(by_date["2026-07-11"]["source_status_json"])["mstr"] == "missing"


# ── (d) OD-12 one date = one row, without an active dedup job ─────


def test_upsert_keeps_one_row_per_date_without_active_dedup():
    header = ["date", "value"]
    existing = ["2026-07-10", "old"]
    sheet = MagicMock()
    sheet.get_all_values.return_value = [header, existing]
    sheet.row_values.return_value = existing

    upsert_rows(sheet, [["2026-07-10", "new"], ["2026-07-11", "fresh"]])

    # Existing date is merged in place (one update), never re-inserted.
    assert sheet.update.call_count == 1
    # Only the genuinely new date is inserted, exactly once.
    assert sheet.insert_row.call_count == 1
    assert sheet.insert_row.call_args.args[0][0] == "2026-07-11"
