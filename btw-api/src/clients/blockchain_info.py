"""
Blockchain.info charts API client.

Free, no authentication required.
Used for: Bitcoin miner hashrate (TH/s → converted to EH/s).
"""

import logging
import requests
from datetime import date

logger = logging.getLogger("btw_api.blockchain_info")

BASE_URL = "https://api.blockchain.info/charts"
TIMEOUT = 30


def fetch_hashrate(start_date: str, end_date: str) -> dict[str, float | None]:
    """
    Fetch daily average miner hashrate in EH/s.

    Blockchain.info returns TH/s — we convert to EH/s (÷ 1_000_000).
    Returns: {date_str: eh_per_second_or_None}
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/hash-rate",
            params={
                "start": start_date,
                "end": end_date,
                "format": "json",
                "sampled": "true",
                "metadata": "false",
                "cors": "true",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Blockchain.info hashrate API failed: %s", exc)
        return {}

    result: dict[str, float | None] = {}
    for point in data.get("values", []):
        d = date.fromtimestamp(point["x"]).isoformat()
        if start_date <= d <= end_date:
            ths = point.get("y")
            result[d] = round(ths / 1_000_000, 4) if ths is not None else None

    logger.debug("Blockchain.info hashrate: %d rows", len(result))
    return result
