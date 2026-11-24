"""
Alternative.me Fear & Greed Index client.

Free API, no authentication required.
Endpoint: https://api.alternative.me/fng/
Returns only the integer value (0–100). value_classification is not stored.
"""

import logging
from datetime import date, timezone
from datetime import datetime

import requests

logger = logging.getLogger("btw_api.fear_greed")

BASE_URL = "https://api.alternative.me/fng/"
TIMEOUT = 15


def fetch_fear_greed(start_date: str, end_date: str) -> dict[str, int]:
    """
    Fetch Fear & Greed index values for a date range.

    Returns: {date_str: value_int}
    API delivers data newest-first; backfill uses limit=3000 (max available ~2018-02-01).
    """
    days_needed = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 3
    # Alternative.me caps at 3000; clamp for large backfills
    limit = min(days_needed, 3000)

    try:
        resp = requests.get(BASE_URL, params={"limit": limit}, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Fear & Greed API failed: %s", exc)
        return {}

    result: dict[str, int] = {}
    for entry in data.get("data", []):
        d = datetime.fromtimestamp(int(entry["timestamp"]), tz=timezone.utc).date().isoformat()
        if start_date <= d <= end_date:
            result[d] = int(entry["value"])

    logger.debug("Fear & Greed: %d entries", len(result))
    return result
