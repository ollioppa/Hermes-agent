"""Contracts for D3: automatic daily refresh mutates only five completed dates."""

from unittest.mock import MagicMock, patch

from src.services import backfill


def _rows_for(day: str) -> list[list[str]]:
    return [["date", "value"], [day, "new-value"]]


def test_daily_default_targets_exactly_five_completed_dates():
    """The default daily run requests rows from D-4 through the completed day D."""
    db_rows = _rows_for("2026-07-11")
    market_rows = _rows_for("2026-07-11")
    macro_rows = [backfill.MACRO_DATA_COLUMNS, ["2026-07-11", *([""] * (len(backfill.MACRO_DATA_COLUMNS) - 1))]]
    market_sheet = MagicMock()
    market_sheet.get_all_values.return_value = [backfill.MARKET_DATA_HEADER]
    macro_sheet = MagicMock()
    macro_sheet.get_all_values.return_value = [backfill.MACRO_DATA_COLUMNS]
    db_sheet = MagicMock()

    with (
        patch.object(backfill, "_latest_completed_daily_date", return_value="2026-07-11"),
        patch.object(backfill, "_build_db_rows", return_value=db_rows) as build_db,
        patch.object(backfill, "_build_market_data_rows", return_value=market_rows) as build_market,
        patch.object(backfill, "_build_macro_data_rows", return_value=macro_rows),
        patch.object(backfill, "get_sheet", side_effect=lambda name: {
            "DB": db_sheet,
            "MARKET_DATA": market_sheet,
            "MACRO_DATA": macro_sheet,
        }[name]),
        patch.object(backfill, "upsert_rows"),
        patch("src.services.windowed_sheets.write_windowed_db_sheets"),
        patch("src.services.windowed_sheets.write_windowed_market_data_sheets"),
    ):
        backfill.run_daily()

    assert build_db.call_args.kwargs["write_start"] == "2026-07-07"
    assert build_market.call_args.kwargs["write_start"] == "2026-07-07"
    assert build_db.call_args.kwargs["end_date"] == "2026-07-11"
    assert build_market.call_args.kwargs["end_date"] == "2026-07-11"


def test_daily_upserts_only_rows_built_for_the_mutable_window():
    """Daily upserts receive only the rows returned for their bounded write window."""
    db_rows = _rows_for("2026-07-11")
    market_rows = _rows_for("2026-07-11")
    macro_rows = [backfill.MACRO_DATA_COLUMNS, ["2026-07-11", *([""] * (len(backfill.MACRO_DATA_COLUMNS) - 1))]]
    market_sheet = MagicMock()
    market_sheet.get_all_values.return_value = [backfill.MARKET_DATA_HEADER]
    macro_sheet = MagicMock()
    macro_sheet.get_all_values.return_value = [backfill.MACRO_DATA_COLUMNS]
    db_sheet = MagicMock()

    with (
        patch.object(backfill, "_latest_completed_daily_date", return_value="2026-07-11"),
        patch.object(backfill, "_build_db_rows", return_value=db_rows),
        patch.object(backfill, "_build_market_data_rows", return_value=market_rows),
        patch.object(backfill, "_build_macro_data_rows", return_value=macro_rows),
        patch.object(backfill, "get_sheet", side_effect=lambda name: {
            "DB": db_sheet,
            "MARKET_DATA": market_sheet,
            "MACRO_DATA": macro_sheet,
        }[name]),
        patch.object(backfill, "upsert_rows") as upsert_rows,
        patch("src.services.windowed_sheets.write_windowed_db_sheets"),
        patch("src.services.windowed_sheets.write_windowed_market_data_sheets"),
    ):
        backfill.run_daily()

    assert upsert_rows.call_args_list[0].args[1] == db_rows[1:]
    assert upsert_rows.call_args_list[1].args[1] == market_rows[1:]


def test_db_builder_excludes_dates_before_its_write_start():
    """A source date older than the mutable window never reaches DB output rows."""
    close_data = {
        "2026-07-06": 100.0,
        "2026-07-07": 101.0,
        "2026-07-11": 102.0,
    }

    with (
        patch.object(backfill, "fetch_btcusdt_close", return_value=close_data),
        patch.object(backfill, "fetch_btc_close", return_value=close_data),
        patch.object(backfill, "_fetch_mstr_close", return_value=close_data),
        patch.object(backfill, "fetch_fear_greed", return_value=close_data),
        patch.object(backfill, "fetch_mvrv", return_value=close_data),
        patch.object(
            backfill,
            "fetch_open_interest_provenance",
            return_value={day: {"value": value, "coverage_pct": 100.0} for day, value in close_data.items()},
        ),
        patch.object(
            backfill,
            "fetch_liquidations",
            return_value={day: {"long": 1.0, "short": 2.0, "total": 3.0} for day in close_data},
        ),
        patch.object(backfill, "fetch_etf_inflows", return_value={}),
        patch.object(backfill, "compute_all", side_effect=lambda frame: frame),
        patch.object(backfill.time, "sleep"),
    ):
        rows = backfill._build_db_rows(
            "2026-07-12T06:00:00+00:00",
            start_override="2026-01-01",
            write_start="2026-07-07",
            end_date="2026-07-11",
        )

    assert [row[0] for row in rows[1:]] == ["2026-07-11", "2026-07-07"]
