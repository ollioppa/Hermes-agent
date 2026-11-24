"""Backfill only the OI family after the BitMEX closure.

Writes exactly five DB columns from the Deribit-backed OI v2 series:
perp_oi_usd, oi_coverage_pct, perp_oi_7d_change_pct,
perp_oi_30d_change_pct, and source_status_json.  All other DB cells remain
untouched.  The pre-write values are backed up and every written cell is read
back verbatim before success is reported.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.clients.coinalyze import fetch_open_interest_provenance
from src.config.settings import OI_BASKET_ID
from src.services.google_sheets import get_sheet, read_all_values
from src.services.indicators import compute_all
from src.scripts.market_briefing_snapshot import numericize

DB_SHEET = "DB"
# Weekly v2 needs 12 retrospective W-SUN slots (84 days) and each daily
# thermometer value needs a prior 180-day OI reference.  Older OI cells retain
# their legacy identity rather than being silently rebased to a market that did
# not exist across their whole range.
WEEKLY_HISTORY_DAYS = 84
OI_REFERENCE_DAYS = 180
TARGET_COLUMNS = (
    "perp_oi_usd",
    "oi_coverage_pct",
    "perp_oi_7d_change_pct",
    "perp_oi_30d_change_pct",
    "source_status_json",
)


def _dates(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def _parse_status(value: Any, day: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as exc:
        raise ValueError(f"{day}: source_status_json is invalid") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{day}: source_status_json is invalid")
    return dict(parsed)


def _fetch_complete(start: date, end: date) -> dict[str, dict[str, Any]]:
    expected = _dates(start, end)
    # Coinalyze's daily-history endpoint returns the requested range in one
    # response.  Splitting it would multiply API credits by the nine symbols.
    received = fetch_open_interest_provenance(start.isoformat(), end.isoformat())
    missing = sorted(set(expected) - set(received))
    if missing:
        raise ValueError(f"Deribit OI is incomplete; first missing dates: {missing[:3]}")
    for day in expected:
        item = received[day]
        if item.get("basket_id") != OI_BASKET_ID or item.get("coverage_pct") != 100.0:
            raise ValueError(f"{day}: Deribit OI provenance is incomplete")
    return received


def _read_sheet() -> tuple[list[str], list[list[Any]], dict[str, int]]:
    values = read_all_values(get_sheet(DB_SHEET), unformatted=True)
    if not values:
        raise ValueError("DB sheet is empty")
    header = [str(value) for value in values[0]]
    missing = set(("date", *TARGET_COLUMNS)) - set(header)
    if missing or len(set(header)) != len(header):
        raise ValueError(f"DB schema invalid; missing={sorted(missing)}")
    return header, values[1:], {name: header.index(name) for name in header}


def _plan(header: list[str], rows: list[list[Any]], indexes: dict[str, int], provenance: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    date_index = indexes["date"]
    by_date: dict[str, tuple[int, list[Any]]] = {}
    for row_number, row in enumerate(rows, start=2):
        if len(row) <= date_index:
            continue
        day = str(row[date_index])
        if day in by_date:
            raise ValueError(f"duplicate DB date: {day}")
        by_date[day] = (row_number, list(row))
    target_dates = sorted(provenance)
    missing = [day for day in target_dates if day not in by_date]
    if missing:
        raise ValueError(f"DB missing Deribit target dates: {missing[:3]}")

    frame_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        record = {name: (row[i] if i < len(row) else None) for i, name in enumerate(header)}
        day = str(record.get("date", ""))
        if day in provenance:
            item = provenance[day]
            status = _parse_status(record.get("source_status_json"), day)
            status["oi"] = "ok"
            status["oi_basket_v1"] = {key: value for key, value in item.items() if key != "value"}
            record["perp_oi_usd"] = item["value"]
            record["oi_coverage_pct"] = item["coverage_pct"]
            record["source_status_json"] = json.dumps(status, sort_keys=True, separators=(",", ":"))
        frame_rows.append(record)
    frame = pd.DataFrame(frame_rows)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = numericize(frame).sort_values("date").reset_index(drop=True)
    recomputed = compute_all(frame).set_index(frame["date"].dt.date.astype(str))

    updates: list[dict[str, Any]] = []
    backup: list[dict[str, Any]] = []
    for day in target_dates:
        row_number, original = by_date[day]
        changed: dict[str, Any] = {}
        before: dict[str, Any] = {}
        for name in TARGET_COLUMNS:
            column = indexes[name]
            old = original[column] if column < len(original) else ""
            value = recomputed.loc[day, name]
            if pd.isna(value):
                value = ""
            elif hasattr(value, "item"):
                value = value.item()
            changed[name] = value
            before[name] = old
        updates.append({"date": day, "row": row_number, "values": changed})
        backup.append({"date": day, "row": row_number, "values": before})
    return updates, backup


def _backup(backup: list[dict[str, Any]], directory: Path, series_start: date) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"oi_deribit_v2_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    payload = {"contract": "oi_deribit_v2_backfill", "series_start": series_start.isoformat(), "columns": list(TARGET_COLUMNS), "original": backup}
    fd, temp = tempfile.mkstemp(dir=directory, prefix=".oi-backup.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return path


def apply_with_backup(indexes: dict[str, int], updates: list[dict[str, Any]], original: list[dict[str, Any]], backup_dir: Path, series_start: date) -> Path:
    sheet = get_sheet(DB_SHEET)
    backup_path = _backup(original, backup_dir, series_start)
    requests = []
    expected: dict[str, Any] = {}
    for update in updates:
        for name, value in update["values"].items():
            column = indexes[name] + 1
            letter = ""
            n = column
            while n:
                n, remainder = divmod(n - 1, 26)
                letter = chr(65 + remainder) + letter
            cell = f"{letter}{update['row']}"
            requests.append({"range": cell, "values": [[value]]})
            expected[cell] = value
    sheet.batch_update(requests, value_input_option="RAW")
    # One complete sheet read keeps the verification request bounded; thousands
    # of individual A1 ranges overflow Google's URL limit.
    rows = read_all_values(sheet, unformatted=True)
    header = [str(value) for value in rows[0]]
    for update in updates:
        row = rows[update["row"] - 1]
        for name, value in update["values"].items():
            actual = row[header.index(name)] if header.index(name) < len(row) else ""
            if actual != value:
                raise RuntimeError(f"read-back mismatch for {name} on {update['date']}; backup retained at {backup_path}")
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill only Deribit OI v2 fields into DB")
    parser.add_argument("--apply", action="store_true", help="write after complete planning; default is read-only")
    parser.add_argument("--backup-dir", type=Path, default=Path(".oi_deribit_v2_backups"))
    args = parser.parse_args()
    header, rows, indexes = _read_sheet()
    dates = [str(row[indexes["date"]]) for row in rows if len(row) > indexes["date"]]
    end = date.fromisoformat(max(dates))
    current_monday = end - timedelta(days=end.weekday())
    series_start = current_monday - timedelta(days=WEEKLY_HISTORY_DAYS + OI_REFERENCE_DAYS)
    provenance = _fetch_complete(series_start, end)
    updates, original = _plan(header, rows, indexes, provenance)
    backup_path = apply_with_backup(indexes, updates, original, args.backup_dir, series_start) if args.apply else None
    print(json.dumps({"mode": "apply" if args.apply else "plan", "series_start": series_start.isoformat(), "series_end": end.isoformat(), "target_days": len(updates), "changed_columns": list(TARGET_COLUMNS), "backup_path": str(backup_path) if backup_path else None}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
