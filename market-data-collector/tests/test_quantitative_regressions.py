"""Synthetic regressions for BTW-05/06/07; no provider or storage I/O."""
import json
from contextlib import ExitStack
from unittest.mock import patch

import pandas as pd
import pytest

from src.clients import coinalyze
from src.config.settings import DB_COLUMNS
from src.services import backfill
from src.services.indicators import compute_all, PARTIAL_WINDOW_METRICS
from src.services.composite_thermometer import build_daily_thermometer, score_fear_greed, score_mvrv, percentile_points
from tests.test_k4_data_contracts import _base_frame
from tests.test_composite_thermometer_v1 import _complete_frame, AS_OF

DAY = "2026-07-10"


def test_absent_market_is_missing_through_real_builder():
    payload = [{"symbol": coinalyze.settings.LIQ_SYMBOLS[0], "history": [{"t": coinalyze._to_unix(DAY), "l": 2, "s": 3}]}]
    with ExitStack() as stack:
        stack.enter_context(patch.object(coinalyze, "_get_with_retry", return_value=payload))
        legacy = coinalyze.fetch_liquidations(DAY, DAY)
        proof = coinalyze.fetch_liquidations_provenance(DAY, DAY)[DAY]
        assert legacy[DAY] == {"long": None, "short": None, "total": None}
        assert proof["total"] is None and proof["coverage_pct"] < 100
        for name in ["fetch_btcusdt_close", "fetch_btc_close", "_fetch_mstr_close", "fetch_fear_greed", "fetch_mvrv"]:
            stack.enter_context(patch.object(backfill, name, return_value={DAY: 100.0}))
        stack.enter_context(patch.object(backfill, "fetch_open_interest_provenance", return_value={}))
        stack.enter_context(patch.object(backfill, "fetch_etf_inflows", return_value={}))
        stack.enter_context(patch.object(backfill.time, "sleep"))
        rows = backfill._build_db_rows("2026-07-11T06:00:00+00:00", start_override=DAY, end_date=DAY)
    row = dict(zip(DB_COLUMNS, rows[1]))
    assert json.loads(row["source_status_json"])["liq"] == "missing"
    assert [row[k] for k in ("liq_daily_long_usd", "liq_daily_short_usd", "liq_daily_total_usd")] == ["", "", ""]


def test_liquidation_basket_coverage_is_per_day_and_ignores_foreign_symbols():
    symbols = coinalyze.settings.LIQ_SYMBOLS
    payload = [{"symbol": symbol, "history": [{"t": coinalyze._to_unix(DAY), "l": 0, "s": 0}]} for symbol in symbols]
    payload[0]["history"].append({"t": coinalyze._to_unix("2026-07-11"), "l": 2, "s": 3})
    payload.append({"symbol": "FOREIGN", "history": [{"t": coinalyze._to_unix(DAY), "l": 999, "s": 999}]})
    with patch.object(coinalyze, "_get_with_retry", return_value=payload):
        result = coinalyze.fetch_liquidations(DAY, "2026-07-11")
    assert result[DAY] == {"long": 0.0, "short": 0.0, "total": 0.0}
    assert result["2026-07-11"] == {"long": None, "short": None, "total": None}


def test_sparse_calendar_windows_emit_but_mark_and_use_exact_oi_anchor():
    dates = pd.date_range("2026-01-01", periods=40, freq="2D")
    frame = _base_frame(dates, liq_daily_total_usd=[10.] * 40, liq_daily_long_usd=[4.] * 40,
                        funding_daily_pct=[.01] * 40, perp_oi_usd=list(range(1, 41)))
    out = compute_all(frame)
    row = out.iloc[-1]
    assert len(out) == len(frame) and isinstance(out.index, pd.RangeIndex)
    assert row.liq_7d_total_usd == 40.0
    assert row.liq_30d_total_usd == 150.0
    assert set(json.loads(row.source_status_json)["partial_windows"]) == set(PARTIAL_WINDOW_METRICS)
    assert pd.isna(row.perp_oi_7d_change_pct)
    assert row.perp_oi_30d_change_pct == 60.0


def test_calendar_boundary_excludes_day_minus_window_and_oi_does_not_fill():
    dates = pd.date_range("2026-01-01", periods=8)
    frame = _base_frame(dates, liq_daily_total_usd=[1000.] + [1.] * 7,
                        liq_daily_long_usd=[500.] + [.5] * 7,
                        fear_greed=[100.] + [10.] * 7, perp_oi_usd=[None] + [10.] * 7)
    row = compute_all(frame).iloc[-1]
    assert row.liq_7d_total_usd == 7.0 and row.fng_7d_median == 10.0
    assert "liq_7d_total_usd" not in json.loads(row.source_status_json)["partial_windows"]
    assert pd.isna(row.perp_oi_7d_change_pct)


@pytest.mark.parametrize("raw", [float("inf"), float("-inf"), float("nan"), -1., 0.])
def test_mvrv_rejects_invalid_ratio(raw):
    assert score_mvrv(raw) is None


@pytest.mark.parametrize("raw", [float("inf"), float("-inf"), float("nan"), -1., 101.])
def test_fear_greed_rejects_invalid_index(raw):
    assert score_fear_greed(raw) is None


def test_domain_endpoints_and_percentile_reference_finiteness():
    assert score_fear_greed(0) == 2 and score_fear_greed(100) == -2
    assert percentile_points(float("inf"), range(180)) is None
    assert percentile_points(0, [float("inf")] + list(range(179))) is None


@pytest.mark.parametrize("column,value", [("mvrv", float("inf")), ("mvrv", 0), ("fear_greed", -1), ("cb_premium_pct", float("inf")), ("perp_oi_usd", float("inf"))])
def test_invalid_score_input_never_produces_complete_score(column, value):
    frame = _complete_frame()
    frame.loc[frame.index[-1], column] = value
    result = build_daily_thermometer(frame, AS_OF.isoformat())
    assert result["status"] == "partial" and result["score"] is None
    json.dumps(result, allow_nan=False)
