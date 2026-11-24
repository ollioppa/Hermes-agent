"""Contract tests for the pure composite_thermometer_v1 builder."""

from datetime import date, timedelta

import pandas as pd
import pytest

from src.config.settings import OI_BASKET_ID, OI_SYMBOLS
from src.services.composite_thermometer import (
    SCORE_SCHEMA_VERSION,
    build_daily_thermometer,
    build_weekly_history,
    bucket_for_score,
    percentile_points,
    score_fear_greed,
    score_mvrv,
)


AS_OF = date(2026, 7, 12)


def _oi_provenance(symbols=None, coverage=100.0, basket_id=OI_BASKET_ID):
    observed = list(OI_SYMBOLS if symbols is None else symbols)
    return {
        "basket_id": basket_id,
        "provider": "coinalyze",
        "endpoint": "/v1/open-interest-history",
        "interval": "daily",
        "field": "c",
        "convert_to_usd": True,
        "expected_symbols": list(OI_SYMBOLS),
        "observed_symbols": observed,
        "expected_symbol_count": len(OI_SYMBOLS),
        "observed_symbol_count": len(observed),
        "coverage_pct": coverage,
    }


def _complete_frame(as_of=AS_OF):
    records = []
    for offset in range(180, -1, -1):
        day = as_of - timedelta(days=offset)
        status = {
            "binance": "ok",
            "coinbase": "ok",
            "mvrv": "ok",
            "fear_greed": "ok",
            "oi": "ok",
            "oi_basket_v1": _oi_provenance(),
        }
        records.append({
            "date": day.isoformat(),
            "btc_binance_close": 100.0,
            "btc_coinbase_close": 100.0,
            "cb_premium_pct": float(offset),
            "perp_oi_usd": float(offset),
            "mvrv": 1.2,
            "fear_greed": 10,
            "source_status_json": status,
        })
    return pd.DataFrame(records)


@pytest.mark.parametrize(
    ("raw", "points"),
    [(1.29, 2), (1.3, 1), (1.49, 1), (1.5, 0), (2.5, 0), (2.50001, -2)],
)
def test_mvrv_boundaries(raw, points):
    assert score_mvrv(raw) == points


@pytest.mark.parametrize(
    ("raw", "points"),
    [(14.99, 2), (15, 1), (24.99, 1), (25, 0), (75, 0), (75.01, -2)],
)
def test_fear_greed_boundaries(raw, points):
    assert score_fear_greed(raw) == points


@pytest.mark.parametrize(
    ("rank", "points"),
    [(36, 2), (37, 1), (72, 1), (73, 0), (108, 0), (109, -1), (144, -1), (145, -2)],
)
def test_percentile_boundaries_use_inclusive_ties(rank, points):
    reference = list(range(1, 181))
    assert percentile_points(rank, reference) == points


@pytest.mark.parametrize(
    ("score", "bucket"),
    [(-8, "E"), (-4, "E"), (-3, "D"), (-1, "D"), (0, "C"), (2, "C"), (3, "B"), (5, "B"), (6, "A"), (8, "A")],
)
def test_bucket_boundaries(score, bucket):
    assert bucket_for_score(score) == bucket


def test_complete_uses_exactly_four_components_and_funding_is_held():
    result = build_daily_thermometer(_complete_frame(), AS_OF.isoformat())

    assert result["score_schema_version"] == SCORE_SCHEMA_VERSION
    assert result["status"] == "complete"
    assert result["score"] == {"value": 8, "min": -8, "max": 8}
    assert result["bucket"] == "A"
    assert set(result["components"]) == {"cb_premium", "oi", "mvrv", "fear_greed"}
    assert result["funding_diagnostic"] == {
        "id": "funding",
        "status": "held",
        "reason_code": "held_no_documented_settlement_aggregation",
        "points": None,
    }


def test_missing_oi_provenance_is_partial_never_a_neutral_score():
    frame = _complete_frame()
    index = frame.index[frame["date"] == AS_OF.isoformat()][0]
    frame.at[index, "source_status_json"] = {
        "binance": "ok", "coinbase": "ok", "mvrv": "ok", "fear_greed": "ok", "oi": "ok"
    }

    result = build_daily_thermometer(frame, AS_OF.isoformat())

    assert result["status"] == "partial"
    assert result["score"] is None
    assert result["bucket"] is None
    assert result["available_component_points"] == {"cb_premium": 2, "mvrv": 2, "fear_greed": 2}
    assert result["missing_components"] == [
        {"id": "oi", "status": "unavailable", "reason_code": "basket_provenance_missing"}
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda provenance: provenance.update(coverage_pct=99.99),
        lambda provenance: provenance.update(observed_symbols=list(OI_SYMBOLS[:-1]), observed_symbol_count=8),
        lambda provenance: provenance.update(observed_symbols=list(OI_SYMBOLS) + ["UNEXPECTED"], observed_symbol_count=10),
        lambda provenance: provenance.update(basket_id="other_basket"),
    ],
)
def test_oi_requires_exact_v1_basket_and_full_coverage(mutate):
    frame = _complete_frame()
    status = frame.loc[frame["date"] == AS_OF.isoformat(), "source_status_json"].iloc[0]
    mutate(status["oi_basket_v1"])

    result = build_daily_thermometer(frame, AS_OF.isoformat())

    assert result["status"] == "partial"
    assert result["score"] is None
    assert result["missing_components"][0]["id"] == "oi"


def test_missing_calendar_day_in_reference_window_is_unavailable():
    frame = _complete_frame()
    frame = frame[frame["date"] != (AS_OF - timedelta(days=90)).isoformat()]

    result = build_daily_thermometer(frame, AS_OF.isoformat())

    assert result["status"] == "partial"
    assert result["missing_components"] == [
        {"id": "cb_premium", "status": "unavailable", "reason_code": "missing_calendar_day_in_180d_window"},
        {"id": "oi", "status": "unavailable", "reason_code": "missing_calendar_day_in_180d_window"},
    ]


def test_weekly_history_has_current_slot_plus_six_historical_slots_and_median_requires_seven_complete_days():
    daily = {}
    complete_week_start = date(2026, 7, 6)
    for index in range(7):
        daily[(complete_week_start + timedelta(days=index)).isoformat()] = {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "status": "complete",
            "score": {"value": index - 3, "min": -8, "max": 8},
        }
    daily["2026-06-28"] = {
        "score_schema_version": SCORE_SCHEMA_VERSION,
        "status": "partial",
        "missing_components": [{"id": "oi", "reason_code": "oi_coverage_not_100"}],
    }

    history = build_weekly_history(daily, AS_OF.isoformat())

    assert len(history) == 7
    assert history[0] == {
        "week_start": "2026-07-06",
        "week_end": "2026-07-12",
        "status": "complete",
        "label": "median_of_complete_daily_scores",
        "median": 0.0,
        "complete_day_count": 7,
        "missing_dates": [],
        "missing_reasons": [],
    }
    assert history[2]["week_start"] == "2026-06-22"
    assert history[2]["status"] == "unavailable"
    assert history[2]["median"] is None
    assert history[2]["complete_day_count"] == 0
    assert history[2]["missing_dates"] == [f"2026-06-{day:02d}" for day in range(22, 29)]


def test_weekly_history_extends_far_enough_for_six_complete_weeks_when_current_week_is_partial():
    daily = {}
    as_of = date(2026, 7, 24)
    for week_start in [date(2026, 7, 13), date(2026, 7, 6), date(2026, 6, 29), date(2026, 6, 22), date(2026, 6, 15), date(2026, 6, 8)]:
        for index in range(7):
            daily[(week_start + timedelta(days=index)).isoformat()] = {
                "score_schema_version": SCORE_SCHEMA_VERSION,
                "status": "complete",
                "score": {"value": 1, "min": -8, "max": 8},
            }
    for day in range(20, 25):
        daily[f"2026-07-{day}"] = {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "status": "complete",
            "score": {"value": 2, "min": -8, "max": 8},
        }

    history = build_weekly_history(daily, as_of.isoformat())

    assert len(history) == 7
    assert history[0]["week_start"] == "2026-07-20"
    assert history[0]["status"] == "unavailable"
    assert history[0]["complete_day_count"] == 5
    complete = [row for row in history[1:] if row["status"] == "complete"]
    assert len(complete) == 6
    assert complete[-1]["week_start"] == "2026-06-08"


def test_weekly_history_keeps_a_six_of_seven_week_as_partial_with_its_median():
    daily = {}
    week_start = date(2026, 7, 6)
    for index in range(6):
        daily[(week_start + timedelta(days=index)).isoformat()] = {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "status": "complete",
            "score": {"value": index, "min": -8, "max": 8},
        }

    history = build_weekly_history(daily, AS_OF.isoformat())

    assert history[0]["status"] == "partial"
    assert history[0]["median"] == 2.5
    assert history[0]["complete_day_count"] == 6
    assert history[0]["missing_dates"] == ["2026-07-12"]
