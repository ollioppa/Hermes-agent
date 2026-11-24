"""
BTC ETF Inflows tracker.

Source: farside.co.uk via Jina AI markdown renderer (no auth required).
Returns net daily total in USD millions → converted to USD.

Format: "11 Jan 2024" dates, parentheses = negative values, "-" = zero/no data.
"""

import logging
import re
import requests
from datetime import datetime

logger = logging.getLogger("market_data_collector.etf_tracker")

FARSIDE_URL = "https://r.jina.ai/https://farside.co.uk/bitcoin-etf-flow-all-data/"
TIMEOUT = 30


def _parse_farside_date(s: str) -> str | None:
    """Convert '11 Jan 2024' to '2024-01-11'."""
    s = s.strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> float | None:
    """
    Parse farside number format:
      '655.3'    → 655.3  (millions USD)
      '(95.1)'   → -95.1  (parentheses = negative)
      '-'        → None   (no data / zero flow)
    Returns value in USD (multiplied by 1_000_000).
    """
    s = s.strip()
    if not s or s == "-":
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        val = float(s.replace(",", ""))
        return round((-val if negative else val) * 1_000_000, 2)
    except ValueError:
        return None


def fetch_etf_inflows(start_date: str, end_date: str) -> dict[str, float | None]:
    """
    Fetch net daily BTC ETF inflows in USD from farside.co.uk.

    Returns: {date_str: net_flow_usd_or_None}
    Values are in USD (farside source is in USD millions).
    """
    try:
        resp = requests.get(FARSIDE_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
    except Exception as exc:
        logger.warning("ETF Tracker (farside via Jina) unavailable: %s", exc)
        return {}

    result: dict[str, float | None] = {}

    # Find markdown table rows: | date | ... | total |
    # Header line contains "Date" and "Total"
    in_table = False
    date_idx = None
    total_idx = None

    for line in text.splitlines():
        if not line.startswith("|"):
            if in_table:
                break  # table ended
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]

        # Detect header row
        if not in_table:
            lower = [c.lower() for c in cells]
            if "date" in lower and "total" in lower:
                date_idx = lower.index("date")
                total_idx = lower.index("total")
                in_table = True
            continue

        # Skip separator rows (--- lines)
        if all(set(c).issubset({"-", " ", ""}) for c in cells):
            continue

        if date_idx is None or total_idx is None or len(cells) <= max(date_idx, total_idx):
            continue

        d = _parse_farside_date(cells[date_idx])
        if d and start_date <= d <= end_date:
            result[d] = _parse_amount(cells[total_idx])

    logger.debug("ETF Tracker (farside): %d rows parsed", len(result))
    return result
