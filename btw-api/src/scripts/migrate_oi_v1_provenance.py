"""Fail-closed planner and opt-in applier for bounded OI-v1 provenance.

The default mode is a read-only plan.  ``--apply`` is intentionally narrow: it
only runs after the complete 640-day plan validates, durably backs up the exact
original ``source_status_json`` cells, writes those cells in one Sheets batch,
and reads every target cell back for exact serialized-value verification.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.clients.coinalyze import fetch_open_interest_provenance
from src.config.settings import OI_BASKET_ID, OI_SYMBOLS
from src.services.google_sheets import get_sheet, read_all_values

VERIFIED_START_DATE = "2024-10-10"
VERIFIED_END_DATE = "2026-07-11"
VERIFIED_DAY_COUNT = 640
MAX_CHUNK_DAYS = 160
CHUNK_PAUSE_SECONDS = 2.0
DB_SHEET_NAME = "DB"
_REQUIRED_DB_COLUMNS = {"date", "perp_oi_usd", "source_status_json"}


def _scope_days() -> list[str]:
    start = date.fromisoformat(VERIFIED_START_DATE)
    end = date.fromisoformat(VERIFIED_END_DATE)
    days = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    ]
    if len(days) != VERIFIED_DAY_COUNT:
        raise RuntimeError("verified OI scope day count no longer equals 640")
    return days


def _as_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite")
    return number


def _parse_status(value: Any, day: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value in (None, ""):
        return {}
    try:
        status = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{day}: source_status_json is not an object") from exc
    if not isinstance(status, dict):
        raise ValueError(f"{day}: source_status_json is not an object")
    return status


def _validated_provenance(day: str, provenance: Any) -> dict[str, Any]:
    if not isinstance(provenance, dict):
        raise ValueError(f"{day}: missing refetched provenance")
    if len(OI_SYMBOLS) != 9:
        raise RuntimeError("configured OI basket must contain exactly nine symbols")
    expected = list(OI_SYMBOLS)
    observed = provenance.get("observed_symbols")
    if (
        provenance.get("basket_id") != OI_BASKET_ID
        or provenance.get("provider") != "coinalyze"
        or provenance.get("endpoint") != "/v1/open-interest-history"
        or provenance.get("interval") != "daily"
        or provenance.get("field") != "c"
        or provenance.get("convert_to_usd") is not True
        or provenance.get("expected_symbols") != expected
        or not isinstance(observed, list)
        or observed != expected
        or provenance.get("expected_symbol_count") != 9
        or provenance.get("observed_symbol_count") != 9
        or _as_number(provenance.get("coverage_pct"), f"{day}: coverage_pct") != 100.0
    ):
        raise ValueError(f"{day}: refetch is not the exact complete OI v1 basket")
    _as_number(provenance.get("value"), f"{day}: refetched OI")
    return {key: value for key, value in provenance.items() if key != "value"}


def plan_verified_oi_provenance_updates(
    db_rows: Iterable[Mapping[str, Any]], refetched: Mapping[str, Mapping[str, Any]]
) -> dict[str, str]:
    """Validate the complete scope before returning source-status-only updates.

    The inputs are never mutated.  Any missing DB row, duplicate, partial
    basket, unexpected date, or value mismatch aborts before a caller receives
    even a partial plan.
    """
    scope_days = _scope_days()
    scope = set(scope_days)
    rows_by_day: dict[str, Mapping[str, Any]] = {}
    for row in db_rows:
        day = row.get("date")
        if day in scope:
            if day in rows_by_day:
                raise ValueError(f"{day}: duplicate DB row in verified scope")
            rows_by_day[day] = row

    missing_rows = sorted(scope - set(rows_by_day))
    if missing_rows:
        raise ValueError(f"missing DB rows in verified scope: {missing_rows[:3]}")
    if set(refetched) != scope:
        missing = sorted(scope - set(refetched))
        extra = sorted(set(refetched) - scope)
        raise ValueError(f"refetch dates must equal the 640-day scope; missing={missing[:3]}, extra={extra[:3]}")

    plan: dict[str, str] = {}
    for day in scope_days:
        row = rows_by_day[day]
        provenance = refetched[day]
        persisted_oi = _as_number(row.get("perp_oi_usd"), f"{day}: DB perp_oi_usd")
        refetched_oi = _as_number(provenance.get("value"), f"{day}: refetched OI")
        if abs(persisted_oi - refetched_oi) > 0.01:
            raise ValueError(f"{day}: OI mismatch exceeds 0.01")
        status = _parse_status(row.get("source_status_json"), day)
        status["oi_basket_v1"] = _validated_provenance(day, provenance)
        plan[day] = json.dumps(status, sort_keys=True, separators=(",", ":"))

    if len(plan) != VERIFIED_DAY_COUNT:
        raise RuntimeError("refusing incomplete OI provenance plan")
    return plan


def _fetch_in_safe_chunks() -> dict[str, dict[str, Any]]:
    days = _scope_days()
    all_refetched: dict[str, dict[str, Any]] = {}
    for start_index in range(0, len(days), MAX_CHUNK_DAYS):
        chunk = days[start_index:start_index + MAX_CHUNK_DAYS]
        received = fetch_open_interest_provenance(chunk[0], chunk[-1])
        overlap = set(all_refetched).intersection(received)
        if overlap:
            raise ValueError(f"duplicate refetched days across chunks: {sorted(overlap)[:3]}")
        all_refetched.update(received)
        if start_index + MAX_CHUNK_DAYS < len(days):
            time.sleep(CHUNK_PAUSE_SECONDS)
    return all_refetched


def _read_db_rows() -> list[dict[str, Any]]:
    values = read_all_values(get_sheet(DB_SHEET_NAME), unformatted=True)
    if not values:
        raise ValueError("DB sheet is empty")
    header = values[0]
    if len(set(header)) != len(header) or not _REQUIRED_DB_COLUMNS.issubset(header):
        raise ValueError(f"DB sheet lacks required columns: {_REQUIRED_DB_COLUMNS}")
    return [dict(zip(header, row)) for row in values[1:] if row]


def _column_letter(column_number: int) -> str:
    """Return the A1 column name for a positive one-based column number."""
    if column_number < 1:
        raise ValueError("sheet column number must be positive")
    result = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _apply_targets(values: list[list[Any]], updates: Mapping[str, str]) -> list[dict[str, Any]]:
    """Bind a complete validated plan to exactly the existing status cells."""
    if not values:
        raise ValueError("DB sheet is empty")
    header = values[0]
    if len(set(header)) != len(header) or not _REQUIRED_DB_COLUMNS.issubset(header):
        raise ValueError(f"DB sheet lacks required columns: {_REQUIRED_DB_COLUMNS}")
    if set(updates) != set(_scope_days()) or len(updates) != VERIFIED_DAY_COUNT:
        raise RuntimeError("refusing apply without the complete verified OI provenance plan")

    date_index = header.index("date")
    status_index = header.index("source_status_json")
    scope = set(_scope_days())
    by_day: dict[str, tuple[int, list[Any]]] = {}
    for row_number, row in enumerate(values[1:], start=2):
        if len(row) <= date_index:
            continue
        day = str(row[date_index])
        if day not in scope:
            continue
        if day in by_day:
            raise ValueError(f"{day}: duplicate DB row in verified scope")
        by_day[day] = (row_number, row)

    missing = sorted(scope - set(by_day))
    if missing:
        raise ValueError(f"missing DB rows in verified scope: {missing[:3]}")

    column = _column_letter(status_index + 1)
    targets: list[dict[str, Any]] = []
    for day in _scope_days():
        row_number, row = by_day[day]
        original = row[status_index] if len(row) > status_index else ""
        targets.append({
            "day": day,
            "range": f"{column}{row_number}",
            "original": original,
            "target": updates[day],
        })
    if len(targets) != VERIFIED_DAY_COUNT:
        raise RuntimeError("refusing incomplete OI provenance apply target set")
    return targets


def _write_backup(targets: list[dict[str, Any]], backup_dir: Path) -> Path:
    """Durably persist the original cells before any remote mutation is attempted."""
    if len(targets) != VERIFIED_DAY_COUNT:
        raise RuntimeError("refusing backup for incomplete OI provenance target set")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"oi_v1_provenance_backup_{timestamp}.json"
    payload = {
        "created_at_utc": timestamp,
        "scope": {
            "start": VERIFIED_START_DATE,
            "end": VERIFIED_END_DATE,
            "day_count": VERIFIED_DAY_COUNT,
        },
        "changed_column": "source_status_json",
        "original_source_status_json": [
            {"date": target["day"], "range": target["range"], "value": target["original"]}
            for target in targets
        ],
    }
    temporary_path = backup_path.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as backup_file:
        json.dump(payload, backup_file, sort_keys=True, separators=(",", ":"))
        backup_file.write("\n")
        backup_file.flush()
        os.fsync(backup_file.fileno())
    temporary_path.replace(backup_path)
    return backup_path


def _verify_readback(sheet: Any, targets: list[dict[str, Any]], backup_path: Path) -> int:
    readback = sheet.batch_get([target["range"] for target in targets])
    if len(readback) != len(targets):
        raise RuntimeError(f"read-back mismatch; backup retained at {backup_path}")
    for target, returned in zip(targets, readback):
        # gspread returns ValueRange (a list subclass); lightweight test or API
        # adapters may return the underlying ValueRange JSON mapping instead.
        returned_values = returned.get("values", []) if isinstance(returned, Mapping) else returned
        actual = (
            returned_values[0][0]
            if isinstance(returned_values, list)
            and len(returned_values) == 1
            and isinstance(returned_values[0], list)
            and len(returned_values[0]) == 1
            else None
        )
        if actual != target["target"]:
            raise RuntimeError(
                f"read-back mismatch for {target['range']}; backup retained at {backup_path}"
            )
    return len(targets)


def apply_verified_oi_provenance_updates(
    sheet: Any,
    values: list[list[Any]],
    updates: Mapping[str, str],
    backup_dir: Path,
) -> tuple[Path, int]:
    """Backup, write only exact status cells in one batch, and verify every cell."""
    targets = _apply_targets(values, updates)
    backup_path = _write_backup(targets, backup_dir)
    sheet.batch_update(
        [{"range": target["range"], "values": [[target["target"]]]} for target in targets],
        value_input_option="RAW",
    )
    return backup_path, _verify_readback(sheet, targets, backup_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan or safely apply the bounded OI v1 provenance migration."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="explicit no-write mode (the default)")
    mode.add_argument("--apply", action="store_true", help="write only verified source_status_json cells")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="local directory for the mandatory pre-write JSON backup",
    )
    args = parser.parse_args(argv)

    sheet = get_sheet(DB_SHEET_NAME)
    values = read_all_values(sheet, unformatted=True)
    if not values:
        raise ValueError("DB sheet is empty")
    header = values[0]
    if len(set(header)) != len(header) or not _REQUIRED_DB_COLUMNS.issubset(header):
        raise ValueError(f"DB sheet lacks required columns: {_REQUIRED_DB_COLUMNS}")
    db_rows = [dict(zip(header, row)) for row in values[1:] if row]

    refetched = _fetch_in_safe_chunks()
    updates = plan_verified_oi_provenance_updates(db_rows, refetched)
    scope = {
        "start": VERIFIED_START_DATE,
        "end": VERIFIED_END_DATE,
        "day_count": VERIFIED_DAY_COUNT,
    }
    backup_path: Path | None = None
    verified_count = 0
    if args.apply:
        backup_dir = args.backup_dir or (Path.cwd() / ".oi_v1_provenance_backups")
        backup_path, verified_count = apply_verified_oi_provenance_updates(
            sheet, values, updates, backup_dir
        )

    print(json.dumps({
        "mode": "apply" if args.apply else "plan_only_no_sheet_writes",
        "scope": scope,
        "scope_start": VERIFIED_START_DATE,
        "scope_end": VERIFIED_END_DATE,
        "verified_day_count": len(updates),
        "verified_count": verified_count,
        "backup_path": str(backup_path) if backup_path is not None else None,
        "changed_column": "source_status_json",
        "planned_dates": list(updates),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
