"""
Backfill and daily refresh service for DB and MARKET_DATA.

Full backfill:
  - Rebuilds DB and MARKET_DATA from historical sources.
  - Overwrites the target sheets via batch_write.
  - Intended for manual use only.

Daily refresh:
  - Fetches only a small lookback window, default 5 days.
  - Upserts rows with merge protection.
  - Intended for crontab.

Run via:
  python -m src.scripts.run_backfill [--dry-run]
  python -m src.scripts.run_daily [--dry-run] [--lookback-days 5]
"""

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from src.config.settings import (
    BACKFILL_START,
    DB_COLUMNS,
    MACRO_DATA_COLUMNS,
    MACRO_DATA_COLUMN_TYPES,
    MACRO_DATA_DAILY_ENABLED,
    MARKET_DATA_COLUMN_ORDER,
    MARKET_DATA_SYMBOL_MAP,
    SECTOR_SYMBOL_MAP,
)

from src.clients.binance import fetch_btcusdt_close
from src.clients.coinbase import fetch_btc_close
from src.clients.fear_greed import fetch_fear_greed
from src.clients.coinmetrics import fetch_mvrv
from src.clients.coinalyze import fetch_open_interest_provenance, fetch_liquidations
from src.clients.etf_flows import fetch_etf_inflows
from src.clients.finra_margin import fetch_finra_margin
from src.clients.macro_fred import fetch_fred_series
from src.clients.hy_oas import load_verified_archive, merge_archive_with_fred
from src.clients.bdc_scores import load_bdc_exports
from src.services.macro_data import (
    build_bdc_family,
    build_finra_family,
    build_hy_oas_family,
    build_liquidity_family,
    build_macro_rows,
    build_backfill_report,
    build_nfci_family,
    validate_macro_rows,
    validate_backfill_report,
    MACRO_FAMILY_VERSION_KEYS,
)
from src.services.indicators import compute_all
from src.services.google_sheets import get_or_create_sheet, get_sheet, batch_write, upsert_rows
from src.utils.logging_utils import setup_logging

logger = setup_logging("btw_api.backfill")

DB_SHEET_NAME = "DB"
MARKET_DATA_SHEET_NAME = "MARKET_DATA"
MACRO_DATA_SHEET_NAME = "MACRO_DATA"

# A source can span several DB cells. A `missing` fetch becomes `kept_prior`
# only when all relevant conditions prove that an older persisted cell survived
# the merge; this is intentionally a DB contract, not generic Sheets behavior.
DB_STATUS_SOURCE_COLUMNS = {
    "binance": ("btc_binance_close",),
    "coinbase": ("btc_coinbase_close",),
    "mstr": ("mstr_close",),
    "fear_greed": ("fear_greed",),
    "mvrv": ("mvrv",),
    "oi": ("perp_oi_usd", "oi_coverage_pct"),
    "liq": ("liq_daily_long_usd", "liq_daily_short_usd", "liq_daily_total_usd"),
}


def _is_empty(value) -> bool:
    return value is None or value == ""


def reconcile_db_source_status(existing: list, incoming: list, merged: list) -> list:
    """Mark a source `kept_prior` when merge-safe upsert retained its old DB cell."""
    status_idx = DB_COLUMNS.index("source_status_json")
    try:
        status = json.loads(incoming[status_idx] or "{}")
    except (TypeError, json.JSONDecodeError):
        return merged

    for source, columns in DB_STATUS_SOURCE_COLUMNS.items():
        if status.get(source) != "missing":
            continue
        indexes = [DB_COLUMNS.index(column) for column in columns]
        retained = all(
            _is_empty(incoming[idx]) and not _is_empty(existing[idx]) and merged[idx] == existing[idx]
            for idx in indexes
        )
        if retained:
            status[source] = "kept_prior"

    reconciled = list(merged)
    reconciled[status_idx] = json.dumps(status, sort_keys=True)
    return reconciled


MACRO_STATUS_FAMILY_COLUMNS = {
    "finra": tuple(
        column
        for column in MACRO_DATA_COLUMNS
        if column.startswith("finra_") or column in {"cpi_index", "sp500_close", "sp500_12m_high"}
    ),
    "nfci": tuple(column for column in MACRO_DATA_COLUMNS if column.startswith("nfci_")),
    "liquidity": tuple(
        column
        for column in MACRO_DATA_COLUMNS
        if column.startswith(("fed_", "walcl_", "wtregen_", "rrp_", "liquidity_"))
    ),
    "hy_oas": tuple(column for column in MACRO_DATA_COLUMNS if column.startswith("hy_oas_"))
    + ("hy_oas",),
    "bdc": tuple(column for column in MACRO_DATA_COLUMNS if column.startswith("bdc_")),
}


def include_existing_macro_dates(
    incoming_rows: list[list[object]],
    existing_values: list[list[object]],
    *,
    write_start: str,
    end_date: str,
    updated_at_utc: str,
) -> list[list[object]]:
    """Add no-data placeholders so sparse persisted dates pass through merge reconciliation."""
    if not incoming_rows or incoming_rows[0] != list(MACRO_DATA_COLUMNS):
        raise MacroDataSchemaError("incoming MACRO_DATA header mismatch")
    incoming_by_date = {str(row[0]): list(row) for row in incoming_rows[1:]}
    status_json = json.dumps(
        {family: "missing" for family in MACRO_STATUS_FAMILY_COLUMNS},
        sort_keys=True,
    )
    status_idx = MACRO_DATA_COLUMNS.index("source_status_json")
    version_idx = MACRO_DATA_COLUMNS.index("calculation_version_json")
    updated_idx = MACRO_DATA_COLUMNS.index("updated_at_utc")
    for existing in existing_values[1:]:
        if not existing:
            continue
        date_value = str(existing[0])
        if not (write_start <= date_value <= end_date) or date_value in incoming_by_date:
            continue
        placeholder: list[object] = [""] * len(MACRO_DATA_COLUMNS)
        placeholder[0] = date_value
        placeholder[status_idx] = status_json
        placeholder[version_idx] = "{}"
        placeholder[updated_idx] = updated_at_utc
        incoming_by_date[date_value] = placeholder
    return [
        list(MACRO_DATA_COLUMNS),
        *[incoming_by_date[key] for key in sorted(incoming_by_date, reverse=True)],
    ]


def reconcile_macro_source_status(existing: list, incoming: list, merged: list) -> list:
    """Replace or retain complete Macro families and expose retained values."""
    status_idx = MACRO_DATA_COLUMNS.index("source_status_json")
    version_idx = MACRO_DATA_COLUMNS.index("calculation_version_json")
    try:
        status = json.loads(incoming[status_idx] or "{}")
    except (TypeError, json.JSONDecodeError):
        return merged
    try:
        existing_versions = json.loads(existing[version_idx] or "{}")
        incoming_versions = json.loads(incoming[version_idx] or "{}")
    except (TypeError, json.JSONDecodeError):
        existing_versions = {}
        incoming_versions = {}
    reconciled = list(merged)
    reconciled_versions = dict(existing_versions)
    for family, columns in MACRO_STATUS_FAMILY_COLUMNS.items():
        indexes = [MACRO_DATA_COLUMNS.index(column) for column in columns]
        family_status = status.get(family)
        incoming_empty = all(_is_empty(incoming[index]) for index in indexes)
        if family_status == "missing" and incoming_empty:
            retained = any(not _is_empty(existing[index]) for index in indexes)
            for index in indexes:
                reconciled[index] = existing[index]
            if retained:
                status[family] = "kept_prior"
            continue
        if family_status not in (None, "missing", "kept_prior"):
            for index in indexes:
                reconciled[index] = incoming[index]
            version_key = MACRO_FAMILY_VERSION_KEYS[family]
            if version_key in incoming_versions:
                reconciled_versions[version_key] = incoming_versions[version_key]
            else:
                reconciled_versions.pop(version_key, None)
    reconciled[status_idx] = json.dumps(status, sort_keys=True)
    reconciled[version_idx] = json.dumps(reconciled_versions, sort_keys=True)
    return reconciled


MARKET_DATA_HEADER = [
    "date",
    *MARKET_DATA_COLUMN_ORDER,
    "btc_etf_total_flow_usd_m",
    "etf_flow_source_status",
    "updated_at_utc",
    *SECTOR_SYMBOL_MAP.values(),
]
END_DATE = date.today().isoformat()


class MarketDataSchemaError(RuntimeError):
    """Raised when incremental writes would target a different column contract."""


class MacroDataSchemaError(RuntimeError):
    """Raised before a positional MACRO_DATA upsert can hit a stale schema."""


def assert_macro_data_header(sheet) -> list[list]:
    values = sheet.get_all_values()
    actual = values[0] if values else []
    if actual != MACRO_DATA_COLUMNS:
        raise MacroDataSchemaError(
            "MACRO_DATA header mismatch; refusing incremental write. "
            f"expected={MACRO_DATA_COLUMNS!r}, actual={actual!r}."
        )
    return values


def assert_market_data_header(sheet) -> None:
    """Fail closed before a positional daily upsert hits a stale MARKET_DATA schema."""
    values = sheet.get_all_values()
    actual = values[0] if values else []
    if actual != MARKET_DATA_HEADER:
        raise MarketDataSchemaError(
            "MARKET_DATA header mismatch; refusing incremental write. "
            f"expected={MARKET_DATA_HEADER!r}, actual={actual!r}. "
            "Run a reviewed, explicit schema migration/full backfill before retrying."
        )
# Daily refresh writes only a small lookback window, but compute_all needs a
# longer history for 200-week MA and rolling regime metrics.
COMPUTE_CONTEXT_DAYS = 1500
MACRO_WRITE_WINDOW_DAYS = 120
MACRO_COMPUTE_CONTEXT_DAYS = 2200

try:
    import yfinance as yf
    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False


def _start_for_lookback(lookback_days: int) -> str:
    return (date.today() - timedelta(days=max(1, lookback_days))).isoformat()


def _start_for_window(end_date: str, days: int) -> str:
    return (date.fromisoformat(end_date) - timedelta(days=max(1, days) - 1)).isoformat()


def _latest_completed_daily_date() -> str:
    # Daily close rows should represent completed calendar days, not the
    # current in-progress BTC candle.
    return (date.today() - timedelta(days=1)).isoformat()


# Preferred stocks pay regular cash dividends; auto_adjust would subtract each payment
# from historical prices, causing a systematic downward drift vs. actual market prices.
# All other tickers (equities, ETFs) keep auto_adjust=True so stock splits are handled.
_RAW_PRICE_SYMBOLS = {"STRK", "STRF", "STRD", "STRC"}


def _fetch_yfinance_close(symbol: str, start_date: str, end_date: str) -> dict[str, float | None]:
    if not _HAS_YFINANCE:
        logger.warning("yfinance not installed — %s data unavailable", symbol)
        return {}
    try:
        ticker = yf.Ticker(symbol)
        # yfinance end is exclusive; add one day so today's row can appear if available.
        yf_end = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
        auto_adjust = symbol not in _RAW_PRICE_SYMBOLS and symbol not in SECTOR_SYMBOL_MAP
        hist = ticker.history(start=start_date, end=yf_end, auto_adjust=auto_adjust)
        if hist.empty:
            logger.warning("yfinance %s returned no rows", symbol)
            return {}
        return {
            str(idx.date()): round(float(row["Close"]), 6)
            for idx, row in hist.iterrows()
            if pd.notna(row.get("Close"))
        }
    except Exception as exc:
        logger.error("yfinance %s failed: %s", symbol, exc)
        return {}


def _fetch_mstr_close(start_date: str, end_date: str) -> dict[str, float | None]:
    data = _fetch_yfinance_close("MSTR", start_date, end_date)
    return {d: (round(v, 2) if v is not None else None) for d, v in data.items()}


def _build_db_rows(
    now_utc: str,
    start_override: str | None = None,
    write_start: str | None = None,
    end_date: str | None = None,
) -> list[list]:
    """Build DB rows. start_override limits API fetch window; write_start limits returned rows."""
    target_end = end_date or END_DATE
    starts = {
        key: start_override or value
        for key, value in BACKFILL_START.items()
    }

    logger.info("Fetching Binance BTCUSDT (%s → %s)...", starts["binance"], target_end)
    binance_data = fetch_btcusdt_close(starts["binance"], target_end)

    logger.info("Fetching Coinbase BTC-USD (%s → %s)...", starts["coinbase"], target_end)
    coinbase_data = fetch_btc_close(starts["coinbase"], target_end)

    logger.info("Fetching MSTR (%s → %s)...", starts["mstr"], target_end)
    mstr_data = _fetch_mstr_close(starts["mstr"], target_end)

    logger.info("Fetching Fear & Greed (%s → %s)...", starts["fear_greed"], target_end)
    fg_data = fetch_fear_greed(starts["fear_greed"], target_end)

    logger.info("Fetching MVRV (%s → %s)...", starts["coinmetrics"], target_end)
    mvrv_data = fetch_mvrv(starts["coinmetrics"], target_end)

    coinalyze_start = starts["coinalyze"]
    logger.info("Fetching Coinalyze OI (%s → %s)...", coinalyze_start, target_end)
    oi_provenance = fetch_open_interest_provenance(coinalyze_start, target_end)
    oi_data = {day: item["value"] for day, item in oi_provenance.items()}
    oi_coverage_pct = {day: item["coverage_pct"] for day, item in oi_provenance.items()}

    # Coinalyze daily funding candles expose a provider-rate snapshot, not a
    # documented daily settlement/cashflow aggregation. Keep the legacy DB
    # field held rather than manufacturing a daily percentage from candle c.
    logger.warning("Holding Coinalyze funding: no documented daily settlement contract")
    funding_data: dict[str, float | None] = {}

    time.sleep(5)
    logger.info("Fetching Coinalyze Liquidations (%s → %s)...", coinalyze_start, target_end)
    liq_data = fetch_liquidations(coinalyze_start, target_end)

    etf_start = starts["etf_flows"] if not start_override else max(starts["etf_flows"], BACKFILL_START["etf_flows"])
    logger.info("Fetching ETF flows (%s → %s)...", etf_start, target_end)
    etf_data = fetch_etf_inflows(etf_start, target_end)

    all_dates = sorted(
        set(binance_data)
        | set(coinbase_data)
        | set(mstr_data)
        | set(fg_data)
        | set(mvrv_data)
        | set(oi_data)
        | set(funding_data)
        | set(liq_data)
    )
    if not all_dates:
        raise RuntimeError("DB run produced no dates")

    records = []
    for d in all_dates:
        liq = liq_data.get(d, {})
        # Liquidations are a write-atomic daily triple. A partial source candle
        # cannot safely update just one side while preserving an older total.
        liq_complete = all(liq.get(key) is not None for key in ("long", "short", "total"))
        source_status: dict[str, object] = {}
        for key, src_data in [
            ("binance", binance_data),
            ("coinbase", coinbase_data),
            ("mstr", mstr_data),
            ("fear_greed", fg_data),
            ("mvrv", mvrv_data),
        ]:
            source_status[key] = "ok" if d in src_data else "missing"
        provenance = oi_provenance.get(d)
        coverage = provenance.get("coverage_pct") if provenance else None
        if d not in oi_data:
            source_status["oi"] = "missing"
        elif coverage is None:
            source_status["oi"] = "coverage_unknown"
        elif coverage >= 100:
            source_status["oi"] = "ok"
        else:
            source_status["oi"] = f"partial_{coverage:g}pct"
        if provenance is not None:
            # Value remains in the existing DB column; only immutable identity
            # and completeness evidence belong in the structured status object.
            source_status["oi_basket_v1"] = {
                key: value for key, value in provenance.items() if key != "value"
            }
        source_status["funding"] = "held_no_daily_contract"
        source_status["liq"] = "ok_usd_v2" if liq_complete else "missing"

        records.append({
            "date": d,
            "btc_binance_close": binance_data.get(d),
            "btc_coinbase_close": coinbase_data.get(d),
            "mstr_close": mstr_data.get(d),
            "fear_greed": fg_data.get(d),
            "mvrv": mvrv_data.get(d),
            "perp_oi_usd": oi_data.get(d),
            "oi_coverage_pct": oi_coverage_pct.get(d),
            "funding_daily_pct": None,
            "liq_daily_long_usd": liq.get("long") if liq_complete else None,
            "liq_daily_short_usd": liq.get("short") if liq_complete else None,
            "liq_daily_total_usd": liq.get("total") if liq_complete else None,
            "btc_etf_total_flow_usd_m": (
                round(etf_data[d] / 1_000_000, 4) if etf_data.get(d) is not None else None
            ),
            "etf_flow_source_status": "ok" if d in etf_data and etf_data[d] is not None else "",
            "source_status_json": json.dumps(source_status),
            "updated_at_utc": now_utc,
        })

    df = pd.DataFrame(records)
    logger.info("Computing DB derived indicators for current run window...")
    df = compute_all(df)
    # Filter to write_start AFTER compute_all so rolling windows have full context.
    if write_start:
        df = df[df["date"] >= write_start]
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    logger.info("DB date range to write: %s → %s (%d days)", df["date"].iloc[-1], df["date"].iloc[0], len(df))

    data_rows = []
    for _, row in df.iterrows():
        data_rows.append([
            "" if (v is None or (isinstance(v, float) and pd.isna(v))) else v
            for v in [row.get(col) for col in DB_COLUMNS]
        ])

    logger.info("Prepared %d DB data rows", len(data_rows))
    if data_rows:
        logger.info("DB sample: %s", data_rows[0])
    return [DB_COLUMNS] + data_rows


def _build_market_data_rows(
    now_utc: str,
    start_override: str | None = None,
    write_start: str | None = None,
    end_date: str | None = None,
) -> list[list]:
    if not _HAS_YFINANCE:
        raise RuntimeError("yfinance not installed — MARKET_DATA run cannot run")

    target_end = end_date or END_DATE
    market_start = start_override or BACKFILL_START["coinbase"]
    logger.info("Fetching MARKET_DATA yfinance assets (%s → %s)...", market_start, target_end)

    series_by_col: dict[str, dict[str, float | None]] = {}
    all_dates: set[str] = set()

    for symbol, column_name in MARKET_DATA_SYMBOL_MAP.items():
        logger.info("Fetching MARKET_DATA %s → %s...", symbol, column_name)
        data = _fetch_yfinance_close(symbol, market_start, target_end)
        series_by_col[column_name] = data
        all_dates |= set(data)

    # ETF proxies use the same provider helper, but price returns exclude dividends.
    for symbol, column_name in SECTOR_SYMBOL_MAP.items():
        data = _fetch_yfinance_close(symbol, market_start, target_end)
        series_by_col[column_name] = data
        all_dates |= set(data)

    etf_start = market_start if market_start > BACKFILL_START["etf_flows"] else BACKFILL_START["etf_flows"]
    logger.info("Fetching MARKET_DATA ETF flows (%s → %s)...", etf_start, target_end)
    etf_data = fetch_etf_inflows(etf_start, target_end)
    etf_flow_m = {
        d: (round(v / 1_000_000, 4) if v is not None else None)
        for d, v in etf_data.items()
    }
    all_dates |= set(etf_flow_m)

    if write_start:
        all_dates = {d for d in all_dates if d >= write_start}
    if not all_dates:
        raise RuntimeError("MARKET_DATA run produced no dates")

    sorted_dates = sorted(all_dates, reverse=True)
    rows = [MARKET_DATA_HEADER]
    for d in sorted_dates:
        row = [d]
        for col in MARKET_DATA_COLUMN_ORDER:
            val = series_by_col.get(col, {}).get(d)
            row.append("" if val is None else val)
        row.append("" if etf_flow_m.get(d) is None else etf_flow_m.get(d))
        row.append("ok" if d in etf_flow_m and etf_flow_m.get(d) is not None else "")
        row.append(now_utc)
        row.extend(series_by_col.get(col, {}).get(d, "") for col in SECTOR_SYMBOL_MAP.values())
        rows.append(row)

    logger.info("Prepared %d MARKET_DATA data rows", len(rows) - 1)
    if len(rows) > 1:
        logger.info("MARKET_DATA sample: %s", rows[1])
    return rows


def _build_macro_data_rows(
    now_utc: str,
    start_override: str | None = None,
    write_start: str | None = None,
    end_date: str | None = None,
    allow_partial: bool = False,
    failures: list[str] | None = None,
) -> list[list[object]]:
    """Fetch Macro histories; full builds fail closed, daily builds degrade by family."""
    target_end = end_date or END_DATE

    def attempt(label: str, operation):
        try:
            result = operation()
            if not result:
                raise RuntimeError(f"{label} produced no data")
            return result
        except Exception:
            if not allow_partial:
                raise
            if failures is not None:
                failures.append(label)
            logger.exception("MACRO_DATA daily family input unavailable: %s", label)
            return []

    def attempt_family(label: str, operation) -> dict[date, dict[str, object]]:
        try:
            result = operation()
            if not result:
                raise RuntimeError(f"{label} produced no data")
            return result
        except Exception:
            if not allow_partial:
                raise
            if failures is not None:
                failures.append(label)
            logger.exception("MACRO_DATA daily family unavailable: %s", label)
            return {}

    finra_rows = attempt("FINRA", fetch_finra_margin)
    cpi_rows = attempt(
        "CPIAUCSL",
        lambda: fetch_fred_series("CPIAUCSL", start_override or "1940-01-01", target_end),
    )
    nfci_rows = attempt(
        "NFCILEVERAGE",
        lambda: fetch_fred_series("NFCILEVERAGE", "1970-01-01", target_end),
    )
    walcl_rows = attempt(
        "WALCL", lambda: fetch_fred_series("WALCL", start_override or "1990-01-01", target_end)
    )
    tga_rows = attempt(
        "WTREGEN", lambda: fetch_fred_series("WTREGEN", start_override or "1990-01-01", target_end)
    )
    rrp_rows = attempt(
        "RRPONTSYD",
        lambda: fetch_fred_series("RRPONTSYD", start_override or "1990-01-01", target_end),
    )
    current_hy_oas = attempt(
        "BAMLH0A0HYM2 current",
        lambda: fetch_fred_series("BAMLH0A0HYM2", start_override or "1990-01-01", target_end),
    )
    archive_hy_oas = attempt("BAMLH0A0HYM2 archive", load_verified_archive)
    merged_hy_oas = (
        attempt(
            "BAMLH0A0HYM2 merge",
            lambda: merge_archive_with_fred(archive_hy_oas, current_hy_oas),
        )
        if archive_hy_oas and current_hy_oas
        else []
    )

    price_start = start_override or "1990-01-01"

    def fetch_spx():
        mapping = _fetch_yfinance_close("^GSPC", price_start, target_end)
        if not mapping:
            mapping = _fetch_yfinance_close("SPY", price_start, target_end)
        return [
            (date.fromisoformat(day), float(value))
            for day, value in mapping.items()
            if value is not None
        ]

    spx_rows = attempt("SPX/SPY", fetch_spx)
    bdc_exports = attempt("BDC inbox", load_bdc_exports)

    finra_family = (
        attempt_family("FINRA family", lambda: build_finra_family(finra_rows, cpi_rows, spx_rows))
        if finra_rows and cpi_rows and spx_rows
        else {}
    )
    nfci_family = attempt_family("NFCI family", lambda: build_nfci_family(nfci_rows)) if nfci_rows else {}
    liquidity_family = (
        attempt_family(
            "liquidity family",
            lambda: build_liquidity_family(walcl_rows, tga_rows, rrp_rows),
        )
        if walcl_rows and tga_rows and rrp_rows
        else {}
    )
    hy_oas_family = (
        attempt_family("HY-OAS family", lambda: build_hy_oas_family(merged_hy_oas, spx_rows))
        if merged_hy_oas and spx_rows
        else {}
    )
    bdc_family = attempt_family("BDC family", lambda: build_bdc_family(bdc_exports)) if bdc_exports else {}

    families = (finra_family, nfci_family, liquidity_family, hy_oas_family, bdc_family)
    rows: list[list[object]]
    if allow_partial and not any(families):
        rows = [list(MACRO_DATA_COLUMNS)]
    else:
        rows = build_macro_rows(
            finra=finra_family,
            nfci=nfci_family,
            liquidity=liquidity_family,
            hy_oas=hy_oas_family,
            bdc=bdc_family,
            updated_at_utc=now_utc,
        )
    if not allow_partial and start_override is None and write_start is None:
        validate_backfill_report(build_backfill_report(rows))
    if write_start:
        rows = [rows[0], *[row for row in rows[1:] if str(row[0]) >= write_start]]
    validate_macro_rows(rows)
    return rows


def run(dry_run: bool = False, sheets: set[str] | None = None) -> dict[str, object] | None:
    """Manual full rebuild, optionally restricted to explicit target tabs."""
    targets = sheets if sheets is not None else {DB_SHEET_NAME, MARKET_DATA_SHEET_NAME}
    allowed = {DB_SHEET_NAME, MARKET_DATA_SHEET_NAME, MACRO_DATA_SHEET_NAME}
    unknown = targets - allowed
    if unknown:
        raise ValueError(f"unknown backfill target sheets: {sorted(unknown)}")
    logger.info("=== Full Backfill START (dry_run=%s, sheets=%s) ===", dry_run, sorted(targets))
    now_utc = datetime.now(tz=timezone.utc).isoformat()
    builders = {
        DB_SHEET_NAME: _build_db_rows,
        MARKET_DATA_SHEET_NAME: _build_market_data_rows,
        MACRO_DATA_SHEET_NAME: _build_macro_data_rows,
    }
    built_rows: dict[str, list[list[object]]] = {}
    for sheet_name in (DB_SHEET_NAME, MARKET_DATA_SHEET_NAME, MACRO_DATA_SHEET_NAME):
        if sheet_name in targets:
            built_rows[sheet_name] = builders[sheet_name](now_utc)

    macro_report = (
        build_backfill_report(built_rows[MACRO_DATA_SHEET_NAME])
        if MACRO_DATA_SHEET_NAME in built_rows
        else None
    )

    for sheet_name in (DB_SHEET_NAME, MARKET_DATA_SHEET_NAME, MACRO_DATA_SHEET_NAME):
        if sheet_name not in targets:
            continue
        rows = built_rows[sheet_name]
        logger.info("Writing %d data rows to %s sheet...", len(rows) - 1, sheet_name)
        if not dry_run:
            if sheet_name == MACRO_DATA_SHEET_NAME:
                batch_write(
                    get_or_create_sheet(
                        sheet_name,
                        rows=max(100, len(rows)),
                        cols=len(MACRO_DATA_COLUMNS),
                    ),
                    rows,
                    dry_run=False,
                    column_types=MACRO_DATA_COLUMN_TYPES,
                )
            else:
                batch_write(get_sheet(sheet_name), rows, dry_run=False)
        else:
            logger.info("[dry-run] Would full-write %d %s rows", len(rows) - 1, sheet_name)

    if macro_report is not None:
        logger.info("MACRO_DATA backfill report: %s", json.dumps(macro_report, sort_keys=True))
    logger.info("=== Full Backfill DONE%s ===", " (dry-run)" if dry_run else "")
    return macro_report


def run_daily(dry_run: bool = False, lookback_days: int = 5) -> dict[str, object]:
    """Cron-safe daily refresh: fetch/upsert only the last N days."""
    logger.info("=== Daily Refresh START (dry_run=%s, lookback_days=%s) ===", dry_run, lookback_days)
    now_utc = datetime.now(tz=timezone.utc).isoformat()
    # upsert_rows is positional. Validate the consumer schema before building
    # data or mutating DB, so a stale MARKET_DATA header cannot create a split run.
    market_sheet = get_sheet(MARKET_DATA_SHEET_NAME)
    assert_market_data_header(market_sheet)
    macro_sheet = None
    macro_existing_values: list[list] = []
    if MACRO_DATA_DAILY_ENABLED:
        macro_sheet = get_sheet(MACRO_DATA_SHEET_NAME)
        macro_existing_values = assert_macro_data_header(macro_sheet)
    target_end = _latest_completed_daily_date()
    refresh_start = _start_for_window(target_end, lookback_days)
    macro_refresh_start = _start_for_window(target_end, MACRO_WRITE_WINDOW_DAYS)
    # Fetch extra history for rolling computations before trimming write rows.
    context_start = _start_for_window(target_end, lookback_days + COMPUTE_CONTEXT_DAYS)
    macro_context_start = _start_for_window(
        target_end, MACRO_WRITE_WINDOW_DAYS + MACRO_COMPUTE_CONTEXT_DAYS
    )

    db_rows = _build_db_rows(now_utc, start_override=context_start, write_start=refresh_start, end_date=target_end)
    market_rows = _build_market_data_rows(
        now_utc,
        start_override=context_start,
        write_start=refresh_start,
        end_date=target_end,
    )
    macro_rows = None
    macro_failures: list[str] = []
    if MACRO_DATA_DAILY_ENABLED:
        macro_rows = _build_macro_data_rows(
            now_utc,
            start_override=macro_context_start,
            write_start=macro_refresh_start,
            end_date=target_end,
            allow_partial=True,
            failures=macro_failures,
        )
        macro_rows = include_existing_macro_dates(
            macro_rows,
            macro_existing_values,
            write_start=macro_refresh_start,
            end_date=target_end,
            updated_at_utc=now_utc,
        )
        validate_macro_rows(macro_rows)
    db_data_rows = db_rows[1:]
    market_data_rows = market_rows[1:]
    macro_data_rows = macro_rows[1:] if macro_rows is not None else []

    logger.info("Upserting %d DB rows...", len(db_data_rows))
    if not dry_run:
        upsert_rows(
            get_sheet(DB_SHEET_NAME),
            db_data_rows,
            dry_run=False,
            merge_row_transform=reconcile_db_source_status,
        )
    else:
        logger.info("[dry-run] Would upsert %d DB rows", len(db_data_rows))

    logger.info("Upserting %d MARKET_DATA rows...", len(market_data_rows))
    if not dry_run:
        upsert_rows(market_sheet, market_data_rows, dry_run=False)
    else:
        logger.info("[dry-run] Would upsert %d MARKET_DATA rows", len(market_data_rows))

    if MACRO_DATA_DAILY_ENABLED:
        logger.info("Upserting %d MACRO_DATA rows...", len(macro_data_rows))
        if not dry_run:
            if macro_sheet is None:
                raise RuntimeError("MACRO_DATA sheet was not validated")
            upsert_rows(
                macro_sheet,
                macro_data_rows,
                dry_run=False,
                merge_row_transform=reconcile_macro_source_status,
            )
        else:
            logger.info("[dry-run] Would upsert %d MACRO_DATA rows", len(macro_data_rows))
    else:
        logger.info("MACRO_DATA daily refresh disabled by activation gate")

    from src.services import windowed_sheets

    window_failures: list[str] = []
    if windowed_sheets.WINDOWED_SHEETS_ENABLED:
        for name, fetched_rows, writer in (
            (DB_SHEET_NAME, db_rows, windowed_sheets.write_windowed_db_sheets),
            (MARKET_DATA_SHEET_NAME, market_rows, windowed_sheets.write_windowed_market_data_sheets),
        ):
            try:
                history = fetched_rows if dry_run else get_sheet(name).get_all_values()
            except Exception:
                logger.exception("Failed to read %s history for windowed export", name)
                window_failures.append(f"*:{name}:read_failed")
                continue
            window_failures.extend(writer(history, target_end, dry_run=dry_run))

    result = {
        "status": "partial" if macro_failures or window_failures else "ok",
        "macro_failures": sorted(set(macro_failures)),
        "window_failures": sorted(set(window_failures)),
    }
    logger.log(logging.WARNING if result["status"] == "partial" else logging.INFO,
               "=== Daily Refresh %s%s === %s",
               result["status"].upper(), " (dry-run)" if dry_run else "", result)
    return result
