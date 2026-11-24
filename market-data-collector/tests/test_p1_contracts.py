"""P1 contracts: OI coverage telemetry and MARKET_DATA schema write gate."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.clients import coinalyze
from src.config.settings import DB_COLUMNS, MARKET_DATA_COLUMN_ORDER, SECTOR_SYMBOL_MAP
from src.services import backfill


DAY = "2026-07-10"
EXPECTED_MARKET_HEADER = [
    "date",
    *MARKET_DATA_COLUMN_ORDER,
    "btc_etf_total_flow_usd_m",
    "etf_flow_source_status",
    "updated_at_utc",
    *SECTOR_SYMBOL_MAP.values(),
]


def _daily_source_data(value=100.0):
    return {DAY: value}


def test_oi_fetch_reports_per_date_coverage_for_the_configured_symbol_universe(monkeypatch):
    monkeypatch.setattr(coinalyze.settings, "OI_SYMBOLS", ["BTCUSDT_PERP.A", "BTCUSD_PERP.A"])
    payload = [
        {"symbol": "BTCUSDT_PERP.A", "history": [{"t": coinalyze._to_unix(DAY), "c": 10}]},
        {"symbol": "BTCUSD_PERP.A", "history": [{"t": coinalyze._to_unix(DAY), "c": None}]},
    ]

    with patch.object(coinalyze, "_get_with_retry", return_value=payload):
        totals, coverage = coinalyze.fetch_open_interest_with_coverage(DAY, DAY)

    assert totals == {DAY: 10.0}
    assert coverage == {DAY: 50.0}


def test_db_builder_persists_oi_coverage_and_status_for_partial_response():
    close_data = _daily_source_data()

    with (
        patch.object(backfill, "fetch_btcusdt_close", return_value=close_data),
        patch.object(backfill, "fetch_btc_close", return_value=close_data),
        patch.object(backfill, "_fetch_mstr_close", return_value=close_data),
        patch.object(backfill, "fetch_fear_greed", return_value=close_data),
        patch.object(backfill, "fetch_mvrv", return_value=close_data),
        patch.object(backfill, "fetch_open_interest_provenance", return_value={
            DAY: {
                "value": 100.0,
                "coverage_pct": 50.0,
            }
        }),
        patch.object(backfill, "fetch_liquidations", return_value={}),
        patch.object(backfill, "fetch_etf_inflows", return_value={}),
        patch.object(backfill, "compute_all", side_effect=lambda frame: frame),
        patch.object(backfill.time, "sleep"),
    ):
        rows = backfill._build_db_rows("2026-07-12T06:00:00+00:00", end_date=DAY)

    row = dict(zip(DB_COLUMNS, rows[1]))
    assert row["oi_coverage_pct"] == 50.0
    assert json.loads(row["source_status_json"])["oi"] == "partial_50pct"


def test_db_builder_persists_complete_oi_basket_provenance_per_day():
    close_data = _daily_source_data()
    provenance = {
        DAY: {
            "value": 100.0,
            "basket_id": "coinalyze_btc_perp_basket_20260712_v1",
            "provider": "coinalyze",
            "endpoint": "/v1/open-interest-history",
            "interval": "daily",
            "field": "c",
            "convert_to_usd": True,
            "expected_symbols": list(coinalyze.settings.OI_SYMBOLS),
            "observed_symbols": list(coinalyze.settings.OI_SYMBOLS),
            "expected_symbol_count": 9,
            "observed_symbol_count": 9,
            "coverage_pct": 100.0,
        }
    }

    with (
        patch.object(backfill, "fetch_btcusdt_close", return_value=close_data),
        patch.object(backfill, "fetch_btc_close", return_value=close_data),
        patch.object(backfill, "_fetch_mstr_close", return_value=close_data),
        patch.object(backfill, "fetch_fear_greed", return_value=close_data),
        patch.object(backfill, "fetch_mvrv", return_value=close_data),
        patch.object(backfill, "fetch_open_interest_provenance", return_value=provenance),
        patch.object(backfill, "fetch_liquidations", return_value={}),
        patch.object(backfill, "fetch_etf_inflows", return_value={}),
        patch.object(backfill, "compute_all", side_effect=lambda frame: frame),
        patch.object(backfill.time, "sleep"),
    ):
        rows = backfill._build_db_rows("2026-07-12T06:00:00+00:00", end_date=DAY)

    row = dict(zip(DB_COLUMNS, rows[1]))
    status = json.loads(row["source_status_json"])
    assert row["perp_oi_usd"] == 100.0
    assert row["oi_coverage_pct"] == 100.0
    assert status["oi"] == "ok"
    assert status["oi_basket_v1"] == {key: value for key, value in provenance[DAY].items() if key != "value"}


def test_daily_market_data_header_guard_blocks_all_writes_on_legacy_schema():
    db_sheet = MagicMock()
    legacy_market_sheet = MagicMock()
    legacy_market_sheet.get_all_values.return_value = [["date", "BTC_ETF_Inflows", "", ""]]

    def get_sheet(name):
        return db_sheet if name == "DB" else legacy_market_sheet

    with (
        patch.object(backfill, "get_sheet", side_effect=get_sheet),
        patch.object(backfill, "_latest_completed_daily_date", return_value="2026-07-11"),
        patch.object(backfill, "_build_db_rows") as build_db,
        patch.object(backfill, "_build_market_data_rows") as build_market,
        patch.object(backfill, "upsert_rows") as upsert,
    ):
        with pytest.raises(backfill.MarketDataSchemaError, match="MARKET_DATA header mismatch"):
            backfill.run_daily()

    build_db.assert_not_called()
    build_market.assert_not_called()
    upsert.assert_not_called()


def test_daily_market_data_header_guard_accepts_exact_current_schema():
    sheet = MagicMock()
    sheet.get_all_values.return_value = [EXPECTED_MARKET_HEADER]

    backfill.assert_market_data_header(sheet)
