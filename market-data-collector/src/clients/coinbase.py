"""
Coinbase Exchange API client.

Free, no authentication required for public market data.
Used for: BTC-USD daily close (Coinbase side of the CB Premium calculation).

Endpoint: https://api.exchange.coinbase.com/products/BTC-USD/candles
Max 300 candles per request → chunked for backfill.

Boundary note: API may return an extra candle at the chunk end boundary.
The date filter (start_date <= d <= end_date) handles deduplication naturally.
"""

import logging
import requests
from datetime import date, timedelta, datetime, timezone

from src.config.settings import COINBASE_CHUNK_DAYS

logger = logging.getLogger("market_data_collector.coinbase")

BASE_URL = "https://api.exchange.coinbase.com"
TIMEOUT = 15


def fetch_btc_close(start_date: str, end_date: str) -> dict[str, float | None]:
    """
    Fetch BTC-USD daily close prices from Coinbase.

    Chunks requests into COINBASE_CHUNK_DAYS windows.
    Returns: {date_str: close_price_or_None}
    """
    result: dict[str, float | None] = {}

    chunk_start = date.fromisoformat(start_date)
    end_dt = date.fromisoformat(end_date)

    while chunk_start <= end_dt:
        chunk_end = min(chunk_start + timedelta(days=COINBASE_CHUNK_DAYS - 1), end_dt)

        start_ts = datetime.combine(chunk_start, datetime.min.time(), tzinfo=timezone.utc)
        # Request end is start of the day AFTER chunk_end so that day's candle is included
        end_ts = datetime.combine(chunk_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        try:
            resp = requests.get(
                f"{BASE_URL}/products/BTC-USD/candles",
                params={
                    "start": start_ts.isoformat(),
                    "end": end_ts.isoformat(),
                    "granularity": 86400,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            candles = resp.json()
        except Exception as exc:
            logger.error("Coinbase candles API failed (%s–%s): %s", chunk_start, chunk_end, exc)
            chunk_start = chunk_end + timedelta(days=1)
            continue

        # Candle: [timestamp_s, low, high, open, close, volume]
        # Coinbase returns newest-first; date filter covers any boundary candle
        for candle in candles:
            ts = candle[0]
            close = candle[4]
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            if start_date <= d <= end_date:
                result[d] = round(float(close), 2)

        chunk_start = chunk_end + timedelta(days=1)

    logger.debug("Coinbase BTC-USD: %d rows", len(result))
    return result
