from __future__ import annotations

import csv
import requests
from datetime import date, datetime


FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
MACRO_FRED_SERIES = {
    "CPIAUCSL",
    "NFCILEVERAGE",
    "WALCL",
    "WTREGEN",
    "RRPONTSYD",
    "BAMLH0A0HYM2",
}


def fetch_fred_series(
    series_id: str,
    observation_start: str,
    observation_end: str,
    timeout: int = 30,
) -> list[tuple[date, float]]:
    """Fetch one explicit FRED history and fail closed on schema/empty drift."""
    if series_id not in MACRO_FRED_SERIES:
        raise ValueError(f"unsupported Macro FRED series: {series_id}")
    response = requests.get(
        FRED_GRAPH_CSV_URL,
        params={"id": series_id, "cosd": observation_start, "coed": observation_end},
        timeout=timeout,
    )
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="strict")

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames or "observation_date" not in reader.fieldnames or series_id not in reader.fieldnames:
        raise ValueError(
            f"FRED schema mismatch for {series_id}: fields={reader.fieldnames!r}"
        )

    rows: list[tuple[date, float]] = []
    for row in reader:
        raw = row.get(series_id)
        if raw in (None, "", "."):
            continue
        try:
            observation_date = datetime.strptime(
                str(row.get("observation_date", ""))[:10], "%Y-%m-%d"
            ).date()
            rows.append((observation_date, float(raw)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid FRED row for {series_id}: {row!r}") from exc
    if not rows:
        raise ValueError(f"FRED {series_id} returned no numeric observations")
    return sorted(rows)
