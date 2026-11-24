"""
Coinalyze API client.

Requires API key (COINALYZE_API_KEY in .env).
Rate limit: 40 calls/minute.

Three daily-history endpoints:
  - open-interest-history  : sum OI in USD across BTC perp markets
  - liquidation-history    : daily long/short liquidation volume across BTC perp markets

Funding history is intentionally not consumed by the production builder: a
Coinalyze daily candle does not document a daily settlement/cashflow contract.
For daily history, Coinalyze can return the requested range in one response.
This matches the working Apps Script implementation for OI and avoids burning
rate limit with many artificial chunks.
"""

import logging
import time
import requests
from datetime import date, datetime, timezone

from src.config import settings

logger = logging.getLogger("market_data_collector.coinalyze")

BASE_URL = "https://api.coinalyze.net/v1"
TIMEOUT = 60

# Added on top of whatever Retry-After says
_RETRY_AFTER_BUFFER = 5.0
# Used only when the API sends no Retry-After header
_RETRY_AFTER_DEFAULT = 60.0


def _headers() -> dict[str, str]:
    return {"api_key": settings.COINALYZE_API_KEY}


def _parse_retry_after(header_value: str | None) -> float:
    """Return seconds to wait: header value + buffer, or default if header absent/unparseable."""
    if header_value is not None:
        try:
            return float(header_value) + _RETRY_AFTER_BUFFER
        except ValueError:
            pass
    return _RETRY_AFTER_DEFAULT


def _get_with_retry(url: str, params: dict) -> list:
    """GET with bounded 429 retries."""
    max_retries = max(0, int(settings.COINALYZE_MAX_RETRIES))
    for attempt in range(max_retries + 1):
        resp = requests.get(url, params=params, headers=_headers(), timeout=TIMEOUT)
        if resp.status_code == 429:
            try:
                body = resp.json()
            except Exception:
                body = resp.text[:300]
            retry_after_raw = resp.headers.get("Retry-After")
            sleep_time = _parse_retry_after(retry_after_raw)
            logger.warning(
                "Coinalyze 429 (attempt %d/%d) | Retry-After=%s → sleeping %.1fs | body=%s",
                attempt + 1, max_retries + 1, retry_after_raw, sleep_time, body,
            )
            if attempt < max_retries:
                time.sleep(sleep_time)
                continue
        resp.raise_for_status()
        return resp.json()
    return []


def _to_unix(d: str) -> int:
    return int(datetime.combine(date.fromisoformat(d), datetime.min.time(), tzinfo=timezone.utc).timestamp())


def fetch_open_interest_provenance(
    start_date: str,
    end_date: str,
    *,
    symbols: list[str] | None = None,
    basket_id: str | None = None,
) -> dict[str, dict]:
    """Return daily OI totals plus explicit immutable basket evidence.

    A null candle is unknown, never zero. Unexpected API symbols are retained
    nowhere: they cannot affect either aggregation or the persisted proof.
    """
    requested_symbols = list(symbols or settings.OI_SYMBOLS)
    requested_basket_id = basket_id or settings.OI_BASKET_ID
    try:
        data = _get_with_retry(
            f"{BASE_URL}/open-interest-history",
            params={
                "symbols": ",".join(requested_symbols),
                "interval": "daily",
                "from": _to_unix(start_date),
                "to": _to_unix(end_date) + 86400,
                "convert_to_usd": "true",
            },
        )
    except Exception as exc:
        logger.error("Coinalyze OI failed (%s–%s): %s", start_date, end_date, exc)
        return {}

    expected_symbols = set(requested_symbols)
    totals: dict[str, float] = {}
    observed_symbols: dict[str, set[str]] = {}
    for market in data:
        symbol = market.get("symbol")
        if symbol not in expected_symbols:
            logger.warning("Coinalyze OI returned unexpected symbol %r; ignoring it", symbol)
            continue
        for candle in market.get("history", []):
            d = datetime.fromtimestamp(candle["t"], tz=timezone.utc).date().isoformat()
            if start_date <= d <= end_date and candle.get("c") is not None:
                totals[d] = totals.get(d, 0.0) + float(candle["c"])
                observed_symbols.setdefault(d, set()).add(symbol)

    result: dict[str, dict] = {}
    for d, symbols in observed_symbols.items():
        ordered_observed = [symbol for symbol in requested_symbols if symbol in symbols]
        result[d] = {
            "value": round(totals[d], 2),
            "basket_id": requested_basket_id,
            "provider": "coinalyze",
            "endpoint": "/v1/open-interest-history",
            "interval": "daily",
            "field": "c",
            "convert_to_usd": True,
            "expected_symbols": list(requested_symbols),
            "observed_symbols": ordered_observed,
            "expected_symbol_count": len(requested_symbols),
            "observed_symbol_count": len(ordered_observed),
            "coverage_pct": round(len(ordered_observed) / len(requested_symbols) * 100, 2),
        }
    logger.debug("Coinalyze OI provenance: %d rows", len(result))
    return result


def fetch_open_interest_with_coverage(start_date: str, end_date: str) -> tuple[dict[str, float], dict[str, float]]:
    """Backward-compatible OI values and coverage projection."""
    provenance = fetch_open_interest_provenance(start_date, end_date)
    return (
        {day: item["value"] for day, item in provenance.items()},
        {day: item["coverage_pct"] for day, item in provenance.items()},
    )


def fetch_open_interest(start_date: str, end_date: str) -> dict[str, float]:
    """Backward-compatible OI-total API; producers require provenance."""
    totals, _coverage = fetch_open_interest_with_coverage(start_date, end_date)
    return totals


def fetch_liquidations_provenance(start_date: str, end_date: str) -> dict[str, dict]:
    """Return fail-closed liquidation totals with daily basket evidence.

    This is a research contract. Unlike the legacy value-only helper below it
    emits no partial totals: a day is usable only if every configured market
    supplies both long and short USD candles.
    """
    try:
        data = _get_with_retry(
            f"{BASE_URL}/liquidation-history",
            params={
                "symbols": ",".join(settings.LIQ_SYMBOLS),
                "interval": "daily",
                "from": _to_unix(start_date),
                "to": _to_unix(end_date) + 86400,
                "convert_to_usd": "true",
            },
        )
    except Exception as exc:
        logger.error("Coinalyze liquidation provenance failed (%s–%s): %s", start_date, end_date, exc)
        return {}

    expected = tuple(settings.LIQ_SYMBOLS)
    observed: dict[str, set[str]] = {}
    incomplete: dict[str, set[str]] = {}
    longs: dict[str, float] = {}
    shorts: dict[str, float] = {}
    seen_days: set[str] = set()
    for market in data:
        symbol = market.get("symbol")
        if symbol not in expected:
            continue
        for candle in market.get("history", []):
            day = datetime.fromtimestamp(candle["t"], tz=timezone.utc).date().isoformat()
            if not start_date <= day <= end_date:
                continue
            seen_days.add(day)
            long_value, short_value = candle.get("l"), candle.get("s")
            if long_value is None or short_value is None:
                incomplete.setdefault(day, set()).add(symbol)
                continue
            observed.setdefault(day, set()).add(symbol)
            longs[day] = longs.get(day, 0.0) + float(long_value)
            shorts[day] = shorts.get(day, 0.0) + float(short_value)

    result: dict[str, dict] = {}
    for day in sorted(seen_days):
        observed_symbols = [
            symbol for symbol in expected
            if symbol in observed.get(day, set()) and symbol not in incomplete.get(day, set())
        ]
        complete = len(observed_symbols) == len(expected) and not incomplete.get(day)
        if complete:
            long_value = round(longs[day], 2)
            short_value = round(shorts[day], 2)
            total_value = round(long_value + short_value, 2)
        else:
            long_value = None
            short_value = None
            total_value = None
        result[day] = {
            "long": long_value,
            "short": short_value,
            "total": total_value,
            "basket_id": "coinalyze_btc_liquidation_basket_20260713_v1",
            "expected_symbols": list(expected),
            "observed_symbols": observed_symbols,
            "expected_symbol_count": len(expected),
            "observed_symbol_count": len(observed_symbols),
            "coverage_pct": round(len(observed_symbols) / len(expected) * 100, 2) if expected else 0.0,
            "provider": "coinalyze",
            "endpoint": "/v1/liquidation-history",
            "interval": "daily",
            "convert_to_usd": True,
        }
    return result


def fetch_liquidations(start_date: str, end_date: str) -> dict[str, dict[str, float | None]]:
    """Daily USD liquidation volumes summed across LIQ_SYMBOLS.

    `convert_to_usd=true` normalizes the mixed base-/quote-denominated
    contract set before aggregation. A missing/null candle field is unknown,
    not zero.
    """
    try:
        data = _get_with_retry(
            f"{BASE_URL}/liquidation-history",
            params={
                "symbols": ",".join(settings.LIQ_SYMBOLS),
                "interval": "daily",
                "from": _to_unix(start_date),
                "to": _to_unix(end_date) + 86400,
                # LIQ_SYMBOLS mixes BASE_ASSET- and QUOTE_ASSET-denominated
                # contracts. The API default is false; explicit conversion is
                # required before aggregating a value labelled USD.
                "convert_to_usd": "true",
            },
        )
    except Exception as exc:
        logger.error("Coinalyze liq failed (%s–%s): %s", start_date, end_date, exc)
        return {}

    longs: dict[str, float] = {}
    shorts: dict[str, float] = {}
    missing_longs: set[str] = set()
    missing_shorts: set[str] = set()
    # Same configured basket authority as fetch_liquidations_provenance.
    # Preserve the legacy side-level missingness contract, but never present
    # an absent market as a complete side (or total).
    expected = set(settings.LIQ_SYMBOLS)
    observed: dict[str, set[str]] = {}
    for market in data:
        symbol = market.get("symbol")
        if symbol not in expected:
            continue
        for candle in market.get("history", []):
            d = datetime.fromtimestamp(candle["t"], tz=timezone.utc).date().isoformat()
            if start_date <= d <= end_date:
                observed.setdefault(d, set()).add(symbol)
                l_val = candle.get("l")
                if l_val is None:
                    missing_longs.add(d)
                else:
                    longs[d] = longs.get(d, 0.0) + float(l_val)
                s_val = candle.get("s")
                if s_val is None:
                    missing_shorts.add(d)
                else:
                    shorts[d] = shorts.get(d, 0.0) + float(s_val)

    result: dict[str, dict[str, float | None]] = {}
    for d in set(longs) | set(shorts) | missing_longs | missing_shorts:
        if observed.get(d, set()) != expected:
            missing_longs.add(d)
            missing_shorts.add(d)
        l = None if d in missing_longs else round(longs.get(d, 0.0), 2)
        s = None if d in missing_shorts else round(shorts.get(d, 0.0), 2)
        result[d] = {"long": l, "short": s, "total": round(l + s, 2) if l is not None and s is not None else None}

    logger.debug("Coinalyze liq: %d rows", len(result))
    return result
