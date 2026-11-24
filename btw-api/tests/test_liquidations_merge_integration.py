"""OD-15 integration contract: client-shaped DB values meet merge protection."""

from unittest.mock import MagicMock, patch

from src.config.settings import DB_COLUMNS
from src.services import backfill
from src.services.google_sheets import upsert_rows


DAY = "2026-07-10"


def _build_row(liq: dict[str, float | None]) -> list:
    close_data = {DAY: 100.0}
    with (
        patch.object(backfill, "fetch_btcusdt_close", return_value=close_data),
        patch.object(backfill, "fetch_btc_close", return_value=close_data),
        patch.object(backfill, "_fetch_mstr_close", return_value=close_data),
        patch.object(backfill, "fetch_fear_greed", return_value=close_data),
        patch.object(backfill, "fetch_mvrv", return_value=close_data),
        patch.object(
            backfill,
            "fetch_open_interest_provenance",
            return_value={DAY: {"value": 100.0, "coverage_pct": 100.0}},
        ),
        patch.object(backfill, "fetch_liquidations", return_value={DAY: liq}),
        patch.object(backfill, "fetch_etf_inflows", return_value={}),
        patch.object(backfill, "compute_all", side_effect=lambda frame: frame),
        patch.object(backfill.time, "sleep"),
    ):
        return backfill._build_db_rows(
            "2026-07-12T06:00:00+00:00", start_override="2026-01-01", write_start=DAY, end_date=DAY
        )[1]


def _merge(row: list) -> list:
    existing = [""] * len(DB_COLUMNS)
    existing[0] = DAY
    for column in ("liq_daily_long_usd", "liq_daily_short_usd", "liq_daily_total_usd"):
        existing[DB_COLUMNS.index(column)] = f"prior-{column}"
    sheet = MagicMock()
    sheet.get_all_values.return_value = [DB_COLUMNS, existing]
    sheet.row_values.return_value = existing
    upsert_rows(sheet, [row])
    return sheet.update.call_args.args[1][0]


def test_unknown_liquidation_values_reach_merge_as_empty_and_preserve_existing_cells():
    merged = _merge(_build_row({"long": None, "short": 5.0, "total": None}))
    assert merged[DB_COLUMNS.index("liq_daily_long_usd")] == "prior-liq_daily_long_usd"
    assert merged[DB_COLUMNS.index("liq_daily_short_usd")] == "prior-liq_daily_short_usd"
    assert merged[DB_COLUMNS.index("liq_daily_total_usd")] == "prior-liq_daily_total_usd"


def test_explicit_zero_reaches_merge_as_value_and_overwrites_existing_cells():
    merged = _merge(_build_row({"long": 0.0, "short": 0.0, "total": 0.0}))
    assert [merged[DB_COLUMNS.index(column)] for column in ("liq_daily_long_usd", "liq_daily_short_usd", "liq_daily_total_usd")] == [0.0, 0.0, 0.0]
