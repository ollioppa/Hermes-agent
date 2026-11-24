"""
CoinMetrics Community API client.

Free tier, no authentication required.
Rate limit: modest; pagination supported.

Metrics used:
  - CapMVRVCur  : Market Value to Realised Value ratio
  - AdrActCnt   : Active address count
"""

import logging
import requests

logger = logging.getLogger("market_data_collector.coinmetrics")

BASE_URL = "https://community-api.coinmetrics.io/v4"
TIMEOUT = 30


def fetch_metrics(
    metrics: list[str],
    start_date: str,
    end_date: str,
    asset: str = "btc",
) -> dict[str, dict[str, float | None]]:
    """
    Fetch one or more daily metrics for a given asset.

    Returns: {date_str: {metric_name: value_or_None}}
    """
    url = f"{BASE_URL}/timeseries/asset-metrics"
    params = {
        "assets": asset,
        "metrics": ",".join(metrics),
        "start_time": f"{start_date}T00:00:00Z",
        "end_time": f"{end_date}T23:59:59Z",
        "frequency": "1d",
        "page_size": 1000,
    }

    result: dict[str, dict[str, float | None]] = {}
    page_params = dict(params)
    while True:
        try:
            resp = requests.get(url, params=page_params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("CoinMetrics API failed: %s", exc)
            return {}

        for entry in data.get("data", []):
            d = entry["time"][:10]  # ISO8601 with nanoseconds — slice is safe
            day: dict[str, float | None] = {}
            for m in metrics:
                raw = entry.get(m)
                day[m] = float(raw) if raw is not None else None
            result[d] = day

        next_token = data.get("next_page_token")
        if not next_token:
            break
        page_params = {**params, "next_page_token": next_token}

    logger.debug("CoinMetrics %s: %d rows", ",".join(metrics), len(result))
    return result


def fetch_mvrv(start_date: str, end_date: str) -> dict[str, float | None]:
    """Fetch MVRV ratio. Returns {date_str: float_or_None}"""
    raw = fetch_metrics(["CapMVRVCur"], start_date, end_date)
    return {d: v.get("CapMVRVCur") for d, v in raw.items()}


def fetch_active_addresses(start_date: str, end_date: str) -> dict[str, float | None]:
    """Fetch active address count. Returns {date_str: float_or_None}"""
    raw = fetch_metrics(["AdrActCnt"], start_date, end_date)
    return {d: v.get("AdrActCnt") for d, v in raw.items()}
