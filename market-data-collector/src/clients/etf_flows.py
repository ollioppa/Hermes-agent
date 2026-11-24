"""BTC ETF net daily inflows from Farside via Jina's text renderer.

The direct Farside page is Cloudflare-protected. The working Jina target is HTTPS:
``https://r.jina.ai/https://farside.co.uk/bitcoin-etf-flow-all-data/``.

Jina has rendered this page in two observed layouts: a Markdown table and a
line-oriented text layout. Both contain Farside's ``Date`` and ``Total`` fields.
Farside values are USD millions; this client returns USD.
"""

import logging
import requests
from datetime import datetime

logger = logging.getLogger("market_data_collector.etf_flows")

# Farside blocks direct HTTP clients. Jina's HTTPS target is the current
# retrieval route. Use the all-data page; /btc/ is only a short recent view.
FARSIDE_URL = "https://r.jina.ai/https://farside.co.uk/bitcoin-etf-flow-all-data/"
TIMEOUT = 30


def _parse_date(s: str) -> str | None:
    s = s.strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> float | None:
    """
    '655.3'  → 655_300_000.0
    '(95.1)' → -95_100_000.0
    '-'      → None
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


def _parse_markdown_table(text: str, start_date: str, end_date: str) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    in_table = False
    date_idx: int | None = None
    total_idx: int | None = None

    for line in text.splitlines():
        if not line.startswith("|"):
            if in_table:
                break
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]
        if not in_table:
            lower = [c.lower() for c in cells]
            if "date" in lower and "total" in lower:
                date_idx = lower.index("date")
                total_idx = lower.index("total")
                in_table = True
            continue

        if all(set(c).issubset({"-", " ", ""}) for c in cells):
            continue
        if date_idx is None or total_idx is None or len(cells) <= max(date_idx, total_idx):
            continue

        d = _parse_date(cells[date_idx])
        if d and start_date <= d <= end_date:
            result[d] = _parse_amount(cells[total_idx])
    return result


def _parse_line_layout(text: str, start_date: str, end_date: str) -> dict[str, float | None]:
    """Parse Jina's current layout: one non-empty field per line."""
    items = [line.strip() for line in text.splitlines() if line.strip()]
    for index, item in enumerate(items):
        if item != "Date":
            continue

        first_row = next((i for i in range(index + 1, len(items)) if _parse_date(items[i])), None)
        if first_row is None:
            continue
        headers = items[index + 1:first_row]
        lower = [header.lower() for header in headers]
        if "total" not in lower:
            continue

        width = len(headers)
        total_idx = lower.index("total")
        result: dict[str, float | None] = {}
        for row_start in range(first_row, len(items)):
            d = _parse_date(items[row_start])
            if not d:
                continue
            values = items[row_start + 1:row_start + 1 + width]
            if len(values) != width:
                continue
            if start_date <= d <= end_date:
                result[d] = _parse_amount(values[total_idx])
        return result
    return {}


def parse_etf_inflows(text: str, start_date: str, end_date: str) -> dict[str, float | None]:
    """Parse either observed Jina rendering of Farside's all-data page."""
    return _parse_markdown_table(text, start_date, end_date) or _parse_line_layout(
        text, start_date, end_date
    )


def fetch_etf_inflows(start_date: str, end_date: str) -> dict[str, float | None]:
    """
    Fetch net daily BTC ETF inflows in USD from farside.co.uk.

    Returns: {date_str: net_flow_usd_or_None}
    """
    try:
        resp = requests.get(FARSIDE_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
    except Exception as exc:
        logger.warning("ETF flows (farside via Jina) unavailable: %s", exc)
        return {}

    result = parse_etf_inflows(text, start_date, end_date)
    logger.debug("ETF flows (farside): %d rows", len(result))
    return result
