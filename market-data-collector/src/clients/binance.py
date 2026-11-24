"""
Binance public API client.

Free, no authentication required for market data.
Used for: BTCUSDT daily close price (reference for Coinbase Premium calculation).

CB Premium = Coinbase BTC-USD close − Binance BTCUSDT close.
GAS used Bitstamp because Binance was 451-blocked from Google servers. VM has no such restriction.
"""

import logging
import requests
from datetime import date, timedelta, datetime, timezone

from src.config.settings import BINANCE_CHUNK_DAYS

logger = logging.getLogger("market_data_collector.binance")

BASE_URL = "https://api.binance.com"
TIMEOUT = 15


def fetch_btcusdt_close(start_date: str, end_date: str) -> dict[str, float | None]:
    """
    Fetch BTCUSDT daily close prices from Binance.

    Chunks requests into BINANCE_CHUNK_DAYS windows (API limit: 1000 candles/request).
    Returns: {date_str: close_price_or_None}
    """
    result: dict[str, float | None] = {}

    chunk_start = date.fromisoformat(start_date)
    end_dt = date.fromisoformat(end_date)

    while chunk_start <= end_dt:
        chunk_end = min(chunk_start + timedelta(days=BINANCE_CHUNK_DAYS - 1), end_dt)

        start_ms = int(
            datetime.combine(chunk_start, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000
        )
        # +1 day so the close of chunk_end is included
        end_ms = int(
            datetime.combine(chunk_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000
        )

        try:
            resp = requests.get(
                f"{BASE_URL}/api/v3/klines",
                params={
                    "symbol": "BTCUSDT",
                    "interval": "1d",
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1000,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            klines = resp.json()
        except Exception as exc:
            logger.error("Binance klines API failed (%s–%s): %s", chunk_start, chunk_end, exc)
            chunk_start = chunk_end + timedelta(days=1)
            continue

        # Kline format: [open_time_ms, open, high, low, close, volume, close_time, ...]
        for kline in klines:
            open_time_ms = kline[0]
            close_price = kline[4]
            d = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc).date().isoformat()
            if start_date <= d <= end_date:
                result[d] = round(float(close_price), 2)

        chunk_start = chunk_end + timedelta(days=1)

    logger.debug("Binance BTCUSDT: %d rows", len(result))
    return result
