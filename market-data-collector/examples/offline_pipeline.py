"""Synthetic acquisition -> unchanged row builders -> real snapshot consumer.

No historical market observations, provider responses or account data are used.
Only acquisition and the Sheet transport are replaced; calculations are production code.
Run from the project root: python -B -m examples.offline_pipeline
"""
import contextlib
import io
import json
import os
from datetime import date, timedelta
from unittest.mock import patch

# Set before importing config; the example never uses a local .env or file logging.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["BTW_LOG_TO_FILE"] = "false"
os.environ["LOG_LEVEL"] = "ERROR"
os.environ["MACRO_DATA_CONSUMER_ENABLED"] = "false"

from src.config.settings import OI_BASKET_ID, OI_SYMBOLS
from src.services import backfill
from src.scripts import market_briefing_snapshot as consumer

AS_OF = "2026-10-18"
STAMP = AS_OF + "T00:00:00+00:00"
DAYS = [(date.fromisoformat(AS_OF) - timedelta(days=i)).isoformat() for i in range(1499, -1, -1)]


def series(base, step):
    return {day: base + step * i for i, day in enumerate(DAYS)}


def synthetic_oi():
    # Schema-shaped synthetic provenance, not evidence of a provider fetch.
    return {day: {
        "value": 1000000.0 + 1000 * i,
        "basket_id": OI_BASKET_ID, "provider": "coinalyze",
        "endpoint": "/v1/open-interest-history", "interval": "daily", "field": "c",
        "convert_to_usd": True, "expected_symbols": list(OI_SYMBOLS),
        "observed_symbols": list(OI_SYMBOLS), "expected_symbol_count": len(OI_SYMBOLS),
        "observed_symbol_count": len(OI_SYMBOLS), "coverage_pct": 100.0,
    } for i, day in enumerate(DAYS)}


class SyntheticReadOnlySheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self, **kwargs):
        return self.rows


def run():
    sources = {
        "fetch_btcusdt_close": series(20000, 10),
        "fetch_btc_close": series(20010, 10),
        "_fetch_mstr_close": series(100, 0.1),
        "fetch_fear_greed": series(45, 0),
        "fetch_mvrv": series(1.6, 0),
        "fetch_open_interest_provenance": synthetic_oi(),
        "fetch_liquidations": {day: {"long": 200000.0, "short": 100000.0, "total": 300000.0} for day in DAYS},
        "fetch_etf_inflows": series(1000000, 0),
    }
    with contextlib.ExitStack() as stack:
        for name, values in sources.items():
            stack.enter_context(patch.object(backfill, name, return_value=values))
        stack.enter_context(patch.object(backfill.time, "sleep"))
        stack.enter_context(patch.object(backfill, "_fetch_yfinance_close", return_value=series(100, 0.1)))
        db = backfill._build_db_rows(STAMP, start_override=DAYS[0], end_date=AS_OF)
        market = backfill._build_market_data_rows(STAMP, start_override=DAYS[0], end_date=AS_OF)

    tables = {"DB": db, "MARKET_DATA": market}
    # Keep get_all_values -> sheet_to_df -> numericize -> main/score/render intact.
    sector_builder = consumer.build_sector_snapshot
    captured = io.StringIO()
    with patch.object(consumer, "get_sheet", side_effect=lambda name: SyntheticReadOnlySheet(tables[name])), \
         patch.object(consumer, "MACRO_DATA_CONSUMER_ENABLED", False), \
         patch.object(consumer, "build_sector_snapshot", side_effect=lambda frame: sector_builder(frame, AS_OF)), \
         contextlib.redirect_stdout(captured):
        consumer.main([])
    # Check the modules actually loaded by this example, not an assumed cwd.
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name, module in list(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            assert Path(module.__file__).resolve().is_relative_to(root), name
    snapshot = json.loads(captured.getvalue())
    assert snapshot["db_date"] == AS_OF
    assert snapshot["score"]["status"] == "complete"
    assert snapshot["sectors"]["status"] == "ready"
    assert len(snapshot["sectors"]["sectors"]) == 11
    assert snapshot["indicators"]["btc"]["current"] == 34990.0
    assert snapshot["indicators"]["btc_200w_ma_usd"]["current"] == 28035.0
    return {
        "input_kind": "SYNTHETIC_ONLY_NOT_MARKET_DATA",
        "warning": "All values and provenance fields below are synthetic; not a live market report or investment signal.",
        "as_of": AS_OF,
        "rows": {name: len(rows) - 1 for name, rows in tables.items()},
        "snapshot": snapshot,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
