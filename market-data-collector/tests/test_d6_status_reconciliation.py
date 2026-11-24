import json
from unittest.mock import MagicMock

from src.config.settings import DB_COLUMNS
from src.services import backfill
from src.services.google_sheets import upsert_rows


def _row(**values):
    row = [""] * len(DB_COLUMNS)
    row[DB_COLUMNS.index("date")] = "2026-07-10"
    for key, value in values.items():
        row[DB_COLUMNS.index(key)] = value
    return row


def test_d6_marks_persisted_prior_value_kept_prior_when_missing_fetch_merges_empty_cell():
    existing = _row(
        btc_coinbase_close=100_000.0,
        source_status_json=json.dumps({"coinbase": "ok", "binance": "ok"}),
    )
    incoming = _row(
        btc_coinbase_close="",
        source_status_json=json.dumps({"coinbase": "missing", "binance": "ok"}),
    )
    merged = _row(
        btc_coinbase_close=100_000.0,
        source_status_json=incoming[DB_COLUMNS.index("source_status_json")],
    )

    reconciled = backfill.reconcile_db_source_status(existing, incoming, merged)

    assert json.loads(reconciled[DB_COLUMNS.index("source_status_json")])["coinbase"] == "kept_prior"


def test_d6_keeps_missing_when_no_prior_cell_was_preserved():
    existing = _row(source_status_json=json.dumps({"coinbase": "missing"}))
    incoming = _row(source_status_json=json.dumps({"coinbase": "missing"}))
    merged = _row(source_status_json=incoming[DB_COLUMNS.index("source_status_json")])

    reconciled = backfill.reconcile_db_source_status(existing, incoming, merged)

    assert json.loads(reconciled[DB_COLUMNS.index("source_status_json")])["coinbase"] == "missing"


def test_d6_liquidation_triple_is_kept_prior_only_when_all_cells_survive():
    existing = _row(
        liq_daily_total_usd=300.0,
        liq_daily_long_usd=125.0,
        liq_daily_short_usd=175.0,
        source_status_json=json.dumps({"liq": "ok_usd_v2"}),
    )
    incoming = _row(
        liq_daily_total_usd="",
        liq_daily_long_usd="",
        liq_daily_short_usd="",
        source_status_json=json.dumps({"liq": "missing"}),
    )
    merged = _row(
        liq_daily_total_usd=300.0,
        liq_daily_long_usd=125.0,
        liq_daily_short_usd=175.0,
        source_status_json=incoming[DB_COLUMNS.index("source_status_json")],
    )

    reconciled = backfill.reconcile_db_source_status(existing, incoming, merged)

    assert json.loads(reconciled[DB_COLUMNS.index("source_status_json")])["liq"] == "kept_prior"


def test_d6_liquidation_triple_stays_missing_when_only_part_of_prior_value_survives():
    existing = _row(
        liq_daily_total_usd=300.0,
        liq_daily_long_usd=125.0,
        liq_daily_short_usd=175.0,
        source_status_json=json.dumps({"liq": "ok_usd_v2"}),
    )
    incoming = _row(
        liq_daily_total_usd="",
        liq_daily_long_usd="",
        liq_daily_short_usd="",
        source_status_json=json.dumps({"liq": "missing"}),
    )
    merged = _row(
        liq_daily_total_usd=300.0,
        liq_daily_long_usd="",
        liq_daily_short_usd=175.0,
        source_status_json=incoming[DB_COLUMNS.index("source_status_json")],
    )

    reconciled = backfill.reconcile_db_source_status(existing, incoming, merged)

    assert json.loads(reconciled[DB_COLUMNS.index("source_status_json")])["liq"] == "missing"


def test_d6_reconciliation_runs_at_actual_merge_boundary():
    existing = _row(
        btc_coinbase_close=100_000.0,
        source_status_json=json.dumps({"coinbase": "ok"}),
    )
    incoming = _row(
        btc_coinbase_close="",
        source_status_json=json.dumps({"coinbase": "missing"}),
    )
    sheet = MagicMock()
    sheet.get_all_values.return_value = [DB_COLUMNS, existing]
    sheet.row_values.return_value = existing

    upsert_rows(sheet, [incoming], merge_row_transform=backfill.reconcile_db_source_status)

    persisted = sheet.update.call_args.args[1][0]
    assert json.loads(persisted[DB_COLUMNS.index("source_status_json")])["coinbase"] == "kept_prior"
