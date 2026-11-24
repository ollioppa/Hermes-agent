"""
DeFi Llama stablecoin API client.

Free, no authentication required.
Used for: Total circulating supply of USDT + USDC (USD-pegged).

Two fetch strategies:
  - fetch_current()    : lightweight list endpoint — for daily jobs (low memory)
  - fetch_historical() : full history per stablecoin — for backfill only (high memory)

Stablecoin IDs:
  USDT = 1
  USDC = 2
"""

import logging
import time
import requests
from datetime import date

logger = logging.getLogger("market_data_collector.defillama")

BASE_URL = "https://stablecoins.llama.fi"
TIMEOUT = 30
STABLECOINS = {"USDT": "1", "USDC": "2"}


# ── Daily / Current ────────────────────────────────────────────────────────────

def fetch_current(target_date: str | None = None) -> float | None:
    """
    Fetch total USDT + USDC circulating supply using the lightweight list endpoint.

    Uses /stablecoins?includePrices=false which returns aggregate totals —
    no per-stablecoin history requests needed.

    target_date: if None, returns today's value. For historical use fetch_historical().
    Returns: total USD value or None on error.
    """
    if target_date and target_date != date.today().isoformat():
        # For non-today dates, must use historical
        logger.warning("fetch_current only returns today's data; use fetch_historical for %s", target_date)
        return None

    try:
        resp = requests.get(f"{BASE_URL}/stablecoins", params={"includePrices": "false"}, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("DeFi Llama list endpoint failed: %s", exc)
        return None

    total = 0.0
    for coin in data.get("peggedAssets", []):
        if coin.get("id") in STABLECOINS.values():
            circulating = coin.get("circulating", {})
            # peggedUSD is the USD-pegged portion
            val = circulating.get("peggedUSD", 0) or 0
            total += float(val)

    logger.debug("DeFi Llama current stablecoin supply: $%.2fB", total / 1e9)
    return round(total, 2) if total else None


# ── Backfill / Historical ─────────────────────────────────────────────────────

def _fetch_history(stablecoin_id: str) -> dict[str, float]:
    """
    Fetch full circulating history for one stablecoin.

    Returns: {date_str: circulating_usd}
    Uses /stablecoin/{id} → data["tokens"] for aggregate totals across all chains.
    """
    try:
        resp = requests.get(f"{BASE_URL}/stablecoin/{stablecoin_id}", timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("DeFi Llama history for id=%s failed: %s", stablecoin_id, exc)
        return {}

    result: dict[str, float] = {}
    # "tokens" contains aggregate supply across all chains (correct level — not chainBalances)
    for entry in data.get("tokens", []):
        ts = entry.get("date")
        val = entry.get("totalCirculatingUSD", {}).get("peggedUSD")
        if ts and val is not None:
            d = date.fromtimestamp(int(ts)).isoformat()
            result[d] = float(val)

    return result


def fetch_historical(start_date: str, end_date: str) -> dict[str, float | None]:
    """
    Fetch USDT + USDC combined supply for a date range from full history.

    WARNING: loads full history (~2017–today) into memory per stablecoin.
    Only use for backfill, not daily jobs.

    Returns: {date_str: total_usd_or_None}
    """
    combined: dict[str, float] = {}

    for name, sid in STABLECOINS.items():
        logger.info("DeFi Llama: fetching full history for %s ...", name)
        history = _fetch_history(sid)
        for d, val in history.items():
            if start_date <= d <= end_date:
                combined[d] = combined.get(d, 0.0) + val
        time.sleep(1)  # polite delay between requests

    return {d: round(v, 2) if v else None for d, v in combined.items()}


def fetch_stablecoin_liquidity(
    start_date: str,
    end_date: str,
    backfill: bool = False,
) -> dict[str, float | None]:
    """
    Unified entry point.

    backfill=False (default): uses lightweight current endpoint (daily job).
    backfill=True: uses full history endpoint (slow, high memory).
    """
    if backfill:
        return fetch_historical(start_date, end_date)

    # Daily job: only need today's value
    val = fetch_current()
    today = date.today().isoformat()
    if val is not None and start_date <= today <= end_date:
        return {today: val}
    return {}
