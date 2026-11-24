"""
Alternative.me Fear & Greed Index API client.

Free API, no authentication required.
Endpoint: https://api.alternative.me/fng/
"""

import logging
from datetime import date, timedelta

import requests

logger = logging.getLogger("market_data_collector.alternative_me")

BASE_URL = "https://api.alternative.me/fng/"
TIMEOUT = 15


def _parse_date(ts: str) -> str:
    """Convert Unix timestamp string to YYYY-MM-DD."""
    return date.fromtimestamp(int(ts)).isoformat()


def fetch_fear_greed(start_date: str, end_date: str) -> dict[str, tuple[int, str]]:
    """
    Fetch Fear & Greed index for date range.

    Returns: {date_str: (value_int, label_str)}
    Example: {"2026-04-24": (39, "Fear")}
    """
    days_needed = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 3
    try:
        resp = requests.get(BASE_URL, params={"limit": days_needed}, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Fear & Greed API failed: %s", exc)
        return {}

    result: dict[str, tuple[int, str]] = {}
    for entry in data.get("data", []):
        d = _parse_date(entry["timestamp"])
        if start_date <= d <= end_date:
            result[d] = (int(entry["value"]), entry["value_classification"])

    logger.debug("Fear & Greed: %d entries fetched", len(result))
    return result
