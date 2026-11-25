"""
Windowed sheet management for rolling 30/90/180-day views.

All windowed sheets are populated from the same full-history load
in run_daily(), filtered to their respective date ranges. No new API calls.
"""

import logging
from datetime import date, timedelta
from src.config.settings import WINDOWED_SHEETS_ENABLED, WINDOWED_SHEET_CONFIG
from src.services.google_sheets import get_sheet_by_id, batch_write

logger = logging.getLogger("market_data_collector.windowed_sheets")


def _filter_rows_by_window(
    data_rows: list[list],
    target_end_date: str,
    days_back: int,
    date_col_index: int = 0,
) -> list[list]:
    """
    Filter data rows to a rolling window [target_end - days_back, target_end].

    Args:
        data_rows: List of rows (header already removed)
        target_end_date: Reference date (YYYY-MM-DD) — typically yesterday
        days_back: Number of days back from target_end_date (inclusive both ends)
        date_col_index: Column index for date (default 0)

    Returns:
        Filtered rows in same order as input (newest-first if input is newest-first)
    """
    if not data_rows:
        return []

    target_end = date.fromisoformat(target_end_date)
    window_start = target_end - timedelta(days=max(1, days_back) - 1)

    filtered = []
    for row in data_rows:
        if not row or len(row) <= date_col_index:
            continue
        try:
            row_date_str = str(row[date_col_index])
            row_date = date.fromisoformat(row_date_str)
            # Include both boundaries
            if window_start <= row_date <= target_end:
                filtered.append(row)
        except (ValueError, IndexError):
            logger.debug(f"Skipping malformed date in row: {row}")
            continue

    logger.info(
        f"Filtered {len(data_rows)} rows to window [{window_start}, {target_end}] "
        f"= {len(filtered)} rows ({days_back}d)"
    )
    return filtered


def write_windowed_db_sheets(
    full_db_rows: list[list],
    target_end_date: str,
    dry_run: bool = False,
) -> list[str]:
    """
    Write full DB rows to 3 windowed sheets (30/90/180d).

    Args:
        full_db_rows: Complete DB rows including header (row[0])
        target_end_date: Reference date for window calculation
        dry_run: If True, log only without writing
    """
    if not WINDOWED_SHEETS_ENABLED:
        logger.info("Windowed sheets disabled; skipping DB write")
        return []

    if not full_db_rows or len(full_db_rows) < 2:
        logger.warning("No DB rows to write to windowed sheets")
        return [] if dry_run else ["*:DB:no_data"]

    header = full_db_rows[0]
    data_rows = full_db_rows[1:]
    failures = []
    if not WINDOWED_SHEET_CONFIG and not dry_run:
        return ["*:DB:not_configured"]

    for window_key, config in WINDOWED_SHEET_CONFIG.items():
        days = config["days"]
        spreadsheet_id = config["spreadsheet_id"]
        sheet_name = "DB"

        if not spreadsheet_id:
            logger.warning(f"Skipping {window_key} DB sheet: SPREADSHEET_ID_{days}D not configured")
            if not dry_run:
                failures.append(f"{window_key}:DB:not_configured")
            continue

        # Filter to window
        windowed_data = _filter_rows_by_window(data_rows, target_end_date, days, date_col_index=0)
        windowed_rows = [header] + windowed_data

        logger.info(
            f"Writing {len(windowed_data)} rows to {window_key} DB sheet"
        )

        if not dry_run:
            try:
                sheet = get_sheet_by_id(spreadsheet_id, sheet_name)
                batch_write(sheet, windowed_rows, dry_run=False)
            except Exception as exc:
                logger.error(f"Failed to write {window_key} DB sheet: {exc}", exc_info=True)
                failures.append(f"{window_key}:DB:write_failed")
        else:
            logger.info(f"[dry-run] Would write {len(windowed_rows)} rows to {window_key} DB")
    return failures


def write_windowed_market_data_sheets(
    full_market_rows: list[list],
    target_end_date: str,
    dry_run: bool = False,
) -> list[str]:
    """
    Write full MARKET_DATA rows to 3 windowed sheets (30/90/180d).

    Same logic as write_windowed_db_sheets but for MARKET_DATA.
    """
    if not WINDOWED_SHEETS_ENABLED:
        logger.info("Windowed sheets disabled; skipping MARKET_DATA write")
        return []

    if not full_market_rows or len(full_market_rows) < 2:
        logger.warning("No MARKET_DATA rows to write to windowed sheets")
        return [] if dry_run else ["*:MARKET_DATA:no_data"]

    header = full_market_rows[0]
    data_rows = full_market_rows[1:]
    failures = []
    if not WINDOWED_SHEET_CONFIG and not dry_run:
        return ["*:MARKET_DATA:not_configured"]

    for window_key, config in WINDOWED_SHEET_CONFIG.items():
        days = config["days"]
        spreadsheet_id = config["spreadsheet_id"]
        sheet_name = "MARKET_DATA"

        if not spreadsheet_id:
            logger.warning(f"Skipping {window_key} MARKET_DATA sheet: SPREADSHEET_ID_{days}D not configured")
            if not dry_run:
                failures.append(f"{window_key}:MARKET_DATA:not_configured")
            continue

        windowed_data = _filter_rows_by_window(data_rows, target_end_date, days, date_col_index=0)
        windowed_rows = [header] + windowed_data

        logger.info(
            f"Writing {len(windowed_data)} rows to {window_key} MARKET_DATA sheet"
        )

        if not dry_run:
            try:
                sheet = get_sheet_by_id(spreadsheet_id, sheet_name)
                batch_write(sheet, windowed_rows, dry_run=False)
            except Exception as exc:
                logger.error(f"Failed to write {window_key} MARKET_DATA sheet: {exc}", exc_info=True)
                failures.append(f"{window_key}:MARKET_DATA:write_failed")
        else:
            logger.info(f"[dry-run] Would write {len(windowed_rows)} rows to {window_key} MARKET_DATA")
    return failures
