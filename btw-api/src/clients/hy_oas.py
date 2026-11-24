from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


SERIES_ID = "BAMLH0A0HYM2"
DEFAULT_ARCHIVE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/macro/BAMLH0A0HYM2_archive_1996_2021.csv"
)
DEFAULT_METADATA_PATH = DEFAULT_ARCHIVE_PATH.with_suffix(".metadata.json")


def _parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def load_verified_archive(
    archive_path: Path = DEFAULT_ARCHIVE_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> list[tuple[date, float]]:
    """Load the committed HY-OAS archive only after byte and span validation."""
    archive_path = Path(archive_path)
    metadata_path = Path(metadata_path)
    metadata = json.loads(metadata_path.read_text())
    actual_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if actual_sha256 != metadata.get("sha256"):
        raise ValueError(
            f"HY-OAS archive checksum mismatch: expected={metadata.get('sha256')} "
            f"actual={actual_sha256}"
        )

    rows: list[tuple[date, float]] = []
    with archive_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "DATE" not in reader.fieldnames or SERIES_ID not in reader.fieldnames:
            raise ValueError("HY-OAS archive schema mismatch")
        for row in reader:
            raw = row.get(SERIES_ID, "")
            if raw in ("", ".", None):
                continue
            try:
                rows.append((_parse_date(str(row.get("DATE", ""))), float(raw)))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid HY-OAS archive row: {row!r}") from exc

    rows.sort()
    if not rows:
        raise ValueError("HY-OAS archive contains no numeric observations")
    if rows[0][0].isoformat() != metadata.get("coverage_start"):
        raise ValueError("HY-OAS archive coverage_start mismatch")
    if rows[-1][0].isoformat() != metadata.get("coverage_end"):
        raise ValueError("HY-OAS archive coverage_end mismatch")
    return rows


def merge_archive_with_fred(
    archive_rows: Iterable[tuple[date, float]],
    fred_rows: Iterable[tuple[date, float]],
) -> list[tuple[date, float, str]]:
    """Merge observations by date; current FRED wins overlap and gaps stay absent."""
    merged: dict[date, tuple[float, str]] = {
        observation_date: (float(value), "archive")
        for observation_date, value in archive_rows
    }
    for observation_date, value in fred_rows:
        merged[observation_date] = (float(value), "current_fred")
    return [
        (observation_date, value, regime)
        for observation_date, (value, regime) in sorted(merged.items())
    ]
