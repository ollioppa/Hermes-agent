"""
Yahoo Finance OHLCV client.

Primary source for BTC-USD, MSTR, and all market assets.
No authentication required.
"""

import logging
import math
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger("btw_api.yahoo_finance")

OHLCV_KEYS = ["Close", "High", "Low", "Open", "Volume"]


def _scalar(val) -> float | None:
    """Extract scalar from potentially Series/array value (fixes yfinance FutureWarning)."""
    if val is None:
        return None
    if isinstance(val, pd.Series):
        if val.empty:
            return None
        val = val.iloc[0]
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def fetch_ohlcv(ticker: str, start_date: str, end_date: str) -> dict[str, dict[str, float]]:
    """
    Fetch daily OHLCV for a single ticker.

    Returns: {date_str: {"Close": x, "High": x, "Low": x, "Open": x, "Volume": x}}
    end_date is inclusive.
    """
    end_dt = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    try:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_dt,
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        logger.error("Yahoo Finance download failed for %s: %s", ticker, exc)
        return {}

    if df.empty:
        logger.warning("Yahoo Finance returned empty data for %s (%s → %s)", ticker, start_date, end_date)
        return {}

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    result: dict[str, dict[str, float]] = {}
    for ts, row in df.iterrows():
        date_str = ts.date().isoformat()
        values: dict[str, float] = {}
        for key in OHLCV_KEYS:
            val = _scalar(row.get(key))
            if val is not None:
                values[key] = round(val, 8)
        if values:
            result[date_str] = values

    logger.debug("Yahoo Finance %s: %d rows returned", ticker, len(result))
    return result


def fetch_multi_close(
    symbols: list[str],
    start_date: str,
    end_date: str,
    key_by_symbol: dict[str, str] | None = None,
    *, auto_adjust: bool = True,
) -> dict[str, dict[str, float]]:
    """
    Fetch daily close prices for multiple symbols in one call.

    key_by_symbol: map {yahoo_symbol: output_key_name}
    Returns: {date_str: {key: close_price}}
    """
    if key_by_symbol is None:
        key_by_symbol = {s: s for s in symbols}

    end_dt = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    try:
        df = yf.download(
            symbols,
            start=start_date,
            end=end_dt,
            progress=False,
            auto_adjust=auto_adjust,
        )
    except Exception as exc:
        logger.error("Yahoo Finance multi-download failed: %s", exc)
        return {}

    if df.empty:
        logger.warning("Yahoo Finance multi-download returned empty data")
        return {}

    # Extract Close prices
    if isinstance(df.columns, pd.MultiIndex):
        close_df = df["Close"]
    else:
        close_df = df[["Close"]]

    result: dict[str, dict[str, float]] = {}
    for ts, row in close_df.iterrows():
        date_str = ts.date().isoformat()
        day_data: dict[str, float] = {}
        for symbol in symbols:
            val = _scalar(row.get(symbol))
            if val is not None:
                col_key = key_by_symbol.get(symbol, symbol)
                day_data[col_key] = round(val, 6)
        if day_data:
            result[date_str] = day_data

    logger.debug("Yahoo Finance multi: %d days returned", len(result))
    return result
