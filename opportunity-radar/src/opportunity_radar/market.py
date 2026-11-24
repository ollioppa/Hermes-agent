from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from typing import Any, Callable

from .models import MarketSnapshot
from .transitions import ContractError

NASDAQ_INFO_URL = "https://api.nasdaq.com/api/quote/{symbol}/info?{query}"
NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def parse_nasdaq_quote(payload: dict[str, Any], symbol: str, role: str, retrieved_at: str) -> MarketSnapshot:
    data = payload.get("data") or {}
    if str(data.get("symbol", "")).upper() != symbol.upper():
        raise ContractError("Nasdaq response does not match requested symbol")
    primary = data.get("primaryData") or {}
    match = re.fullmatch(r"\$([0-9,]+(?:\.[0-9]+)?)", str(primary.get("lastSalePrice") or "").strip())
    if match is None:
        raise ContractError(f"Nasdaq returned no usable last-sale price for {symbol}")
    price = float(match.group(1).replace(",", ""))
    if not math.isfinite(price) or price <= 0:
        raise ContractError("Nasdaq price must be finite and positive")
    date_match = re.match(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}", str(primary.get("lastTradeTimestamp") or "").strip())
    try:
        if date_match is None:
            raise ValueError("missing date prefix")
        price_date = datetime.strptime(date_match.group(0), "%b %d, %Y").date().isoformat()
    except ValueError as exc:
        raise ContractError(f"Nasdaq returned no usable trade date for {symbol}") from exc
    if date.fromisoformat(price_date) > datetime.fromisoformat(retrieved_at.replace('Z', '+00:00')).date():
        raise ContractError("Nasdaq trade date is in the future")
    return MarketSnapshot(symbol.upper(), role, price, price_date, retrieved_at, "USD", "nasdaq_info",
                          "last sale price; price return only; not total return")


class NasdaqInfoProvider:
    def __init__(self, opener: Callable[..., Any] = urllib.request.urlopen, reference_date: str | None = None) -> None:
        self._opener, self.reference_date = opener, reference_date

    def fetch(self, symbol: str, kind: str, role: str) -> MarketSnapshot:
        if kind not in {"stock", "etf"}:
            raise ContractError("Nasdaq asset kind must be stock or etf")
        query = urllib.parse.urlencode({"assetclass": "stocks" if kind == "stock" else "etf"})
        request = urllib.request.Request(NASDAQ_INFO_URL.format(symbol=urllib.parse.quote(symbol.upper()), query=query), headers=NASDAQ_HEADERS)
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            with self._opener(request, timeout=30) as response:
                payload = json.load(response)
        except Exception as exc:
            raise ContractError(f"Nasdaq quote fetch failed for {symbol}: {exc}") from exc
        quote = parse_nasdaq_quote(payload, symbol, role, retrieved_at)
        if self.reference_date is not None:
            # Auxiliary unit-event evidence only; never substitute a Yahoo price.
            unit_quote = YahooChartProvider(symbol, "USD", reference_date=self.reference_date).fetch(symbol, kind, role)
            quote = MarketSnapshot(**{**quote.__dict__, "semantics": quote.semantics + " |units=" + unit_quote.semantics.split(" |units=", 1)[1]})
        return quote


class YahooChartProvider:
    """Explicit quote binding from the original snapshot, never a fallback."""
    def __init__(self, quote_symbol: str, currency: str, opener: Callable[..., Any] = urllib.request.urlopen, reference_date: str | None = None) -> None:
        self.quote_symbol, self.currency, self._opener = quote_symbol, currency, opener
        self.reference_date = reference_date

    def history(self, symbol: str, kind: str, role: str) -> dict[str, MarketSnapshot]:
        if kind not in {"stock", "etf"}:
            raise ContractError("Yahoo asset kind must be stock or etf")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(self.quote_symbol, safe='')}?range=5d&interval=1d&events=splits"
        if self.reference_date is not None:
            since = int(datetime.combine(date.fromisoformat(self.reference_date), datetime.min.time(), timezone.utc).timestamp())
            url = url.split("?", 1)[0] + f"?period1={since}&period2={int(datetime.now(timezone.utc).timestamp())}&interval=1d&events=splits"
        now = datetime.now(timezone.utc)
        retrieved_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            with self._opener(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
                result = json.load(response)["chart"]["result"][0]
            meta = result["meta"]
            if (meta["symbol"].upper() != self.quote_symbol.upper() or meta["currency"] != self.currency
                    or meta.get("instrumentType") != ("EQUITY" if kind == "stock" else "ETF")):
                raise ContractError("Yahoo response does not match bound listing/currency")
            zone = ZoneInfo(meta["exchangeTimezoneName"])
            regular_end = meta["currentTradingPeriod"]["regular"]["end"]
            quotes = result["indicators"]["quote"][0]["close"]
            timestamps = result["timestamp"]
            if len(quotes) != len(timestamps):
                raise ContractError("Yahoo daily bars are misaligned")
            since = max(self.reference_date or "0001-01-01", datetime.fromtimestamp(min(timestamps), zone).date().isoformat())
            breaks = sorted({datetime.fromtimestamp(int(event["date"]), zone).date().isoformat()
                             for event in result.get("events", {}).get("splits", {}).values()})
            unit_evidence = json.dumps({"since": since, "through": now.astimezone(zone).date().isoformat(),
                                        "breaks": breaks, "source": "Yahoo declared split/ratio events"}, sort_keys=True)
            rows = {}
            for stamp, price in zip(timestamps, quotes):
                day = datetime.fromtimestamp(stamp, zone).date()
                if day > now.astimezone(zone).date() or (day == now.astimezone(zone).date() and now.timestamp() < regular_end):
                    continue
                if price is None or not math.isfinite(float(price)) or float(price) <= 0:
                    continue
                rows[day.isoformat()] = MarketSnapshot(symbol.upper(), role, float(price), day.isoformat(), retrieved_at,
                    self.currency, f"yahoo_chart:{self.quote_symbol}", "unadjusted regular-session close |units=" + unit_evidence)
            if not rows:
                raise ContractError("Yahoo returned no completed daily close")
            return rows
        except ContractError:
            raise
        except Exception as error:
            raise ContractError(f"Yahoo chart fetch failed for {self.quote_symbol}: {error}") from error

    def fetch(self, symbol: str, kind: str, role: str) -> MarketSnapshot:
        rows = self.history(symbol, kind, role)
        return rows[max(rows)]


def bound_snapshots(connection: Any, case_id: int) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """SELECT CASE m.id WHEN s.case_snapshot_id THEN 'case'
                       WHEN s.spy_snapshot_id THEN 'spy' ELSE 'sector' END binding,m.*
           FROM shadow_entries s JOIN market_snapshots m
             ON m.id IN (s.case_snapshot_id,s.spy_snapshot_id,s.sector_snapshot_id)
           WHERE s.case_id=?""", (case_id,),
    ).fetchall()
    refs = {row["binding"]: dict(row) for row in rows}
    case = connection.execute("SELECT symbol,sector_symbol FROM cases WHERE id=?", (case_id,)).fetchone()
    if case is None or set(refs) != {'case', 'spy', 'sector'}:
        raise ContractError('market comparison requires a complete shadow binding')
    if any(refs[key]['case_id'] != case_id for key in refs):
        raise ContractError('shadow snapshot belongs to another case')
    expected = {'case': case['symbol'], 'spy': 'SPY', 'sector': case['sector_symbol']}
    if any(str(refs[key]['symbol']).upper() != str(expected[key]).upper() for key in refs):
        raise ContractError('shadow symbols do not match case binding')
    for key, ref in refs.items():
        if ref['role'] != {'case': 'case', 'spy': 'benchmark', 'sector': 'sector'}[key]:
            raise ContractError('invalid shadow snapshot role')
    compare_price_sets(refs, refs)
    return {key: canonical_snapshot(ref) for key, ref in refs.items()}


def canonical_snapshot(snapshot: Any) -> dict[str, Any]:
    ref = dict(snapshot)
    MarketSnapshot(**{field: ref[field] for field in MarketSnapshot.__dataclass_fields__})
    semantics, _, units = str(ref['semantics']).partition(' |units=')
    try:
        ref['units'] = json.loads(units) if units else ref.get('units')
        if ref['units'] is not None:
            for day in [ref['units']['since'], ref['units']['through'], *ref['units']['breaks']]:
                if date.fromisoformat(day).isoformat() != day:
                    raise ValueError('noncanonical unit evidence date')
    except (ValueError, TypeError, KeyError) as error:
        raise ContractError('invalid price-unit evidence') from error
    ref['semantics'] = semantics
    provider = str(ref['provider'])
    # Observed Yahoo labels only: retain explicit AD.AS/EUR and TM/USD-ADR listings.
    quote_symbol = provider.split(':', 1)[1] if provider.startswith('yahoo_chart:') else (
        ref['symbol'] if provider in {'yahoo_chart', 'Yahoo Finance chart API'} and ref['currency'] == 'USD' else None)
    if quote_symbol and not str(ref['semantics']).startswith(('unadjusted ', 'regular-session close')):
        quote_symbol = None
    ref['quote_symbol'] = quote_symbol
    ref['canonical_provider'] = f'yahoo_chart:{quote_symbol}' if quote_symbol else provider
    ref['canonical_semantics'] = 'unadjusted regular-session close' if quote_symbol else ref['semantics']
    return ref


def compare_price_sets(start: Any, end: Any) -> dict[str, Any]:
    """Bound local instrument price returns, without FX or dividends."""
    keys = {'case', 'spy', 'sector'}
    if set(start) != keys or set(end) != keys:
        raise ContractError('price comparison requires complete endpoint sets')
    start = {key: canonical_snapshot(row) for key, row in start.items()}
    end = {key: canonical_snapshot(row) for key, row in end.items()}
    for rows in (start, end):
        if len({row['price_date'] for row in rows.values()}) != 1:
            raise ContractError('endpoint set requires one actual trade date')
        if (rows['case']['role'] not in {'case', 'ready', 'outcome'}
                or rows['spy']['role'] != 'benchmark' or rows['sector']['role'] != 'sector'):
            raise ContractError('invalid endpoint roles')
    if end['case']['price_date'] < start['case']['price_date']:
        raise ContractError('price comparison end precedes start')
    returns = {}
    for key in keys:
        if any(start[key][field] != end[key][field] for field in
               ('symbol', 'currency', 'canonical_provider', 'canonical_semantics')):
            raise ContractError('price comparison does not match bound symbol/provider/currency/semantics')
        same_observation = (all(start[key][field] == end[key][field]
                                for field in MarketSnapshot.__dataclass_fields__ if field != 'role')
                            and start[key]['units'] == end[key]['units'])
        if not same_observation:
            units = end[key]['units']
            if not units or units['since'] > start[key]['price_date'] or units['through'] < end[key]['price_date']:
                raise ContractError('price units unresolved: no interval event coverage')
            evidence = [row['units'] for row in (start[key], end[key]) if row['units']]
            if any(start[key]['price_date'] <= day <= max(item['through'] for item in evidence)
                   for item in evidence for day in item['breaks']):
                raise ContractError('price units unresolved: split/ratio event crosses stored endpoints')
        returns[key] = (float(end[key]['price']) / float(start[key]['price']) - 1) * 100
        if not math.isfinite(returns[key]):
            raise ContractError('price return must be finite')
    return {'case_return_pct': returns['case'], 'spy_return_pct': returns['spy'],
            'sector_return_pct': returns['sector'],
            'relative_to_spy_pp': returns['case'] - returns['spy'],
            'relative_to_sector_pp': returns['case'] - returns['sector'],
            'return_basis': 'local instrument price return; no FX or dividends; not total return'}


def snapshot_set(connection: Any, case_id: int, ids: Any) -> dict[str, Any]:
    rows = {}
    for key in ('case', 'spy', 'sector'):
        row = connection.execute('SELECT * FROM market_snapshots WHERE id=? AND case_id=?',
                                 (ids[key + '_snapshot_id'], case_id)).fetchone()
        if row is None:
            raise ContractError('endpoint snapshot is missing or belongs to another case')
        rows[key] = dict(row)
    return rows


def latest_market_metrics(connection: Any, case_id: int) -> dict[str, Any] | None:
    """Current display selection; historical evaluation uses explicit endpoint IDs."""
    try:
        refs = bound_snapshots(connection, case_id)
    except ContractError:
        return None
    rows = connection.execute(
        """SELECT c.id case_snapshot_id,s.id spy_snapshot_id,x.id sector_snapshot_id
           FROM market_snapshots c
           JOIN market_snapshots s ON s.case_id=c.case_id AND s.role='benchmark' AND s.price_date=c.price_date
           JOIN market_snapshots x ON x.case_id=c.case_id AND x.role='sector' AND x.price_date=c.price_date
           WHERE c.case_id=? AND (
             c.role='case'
             OR (c.role='ready' AND EXISTS (
               SELECT 1 FROM ready_snapshot_sets r WHERE r.case_id=c.case_id
               AND r.case_snapshot_id=c.id AND r.spy_snapshot_id=s.id AND r.sector_snapshot_id=x.id))
             OR (c.role='outcome' AND EXISTS (
               SELECT 1 FROM outcome_checks o WHERE o.case_id=c.case_id
               AND o.case_snapshot_id=c.id AND o.spy_snapshot_id=s.id AND o.sector_snapshot_id=x.id)))
           ORDER BY c.price_date DESC,c.id DESC,s.id DESC,x.id DESC""", (case_id,),
    ).fetchall()
    for row in rows:
        try:
            endpoint = snapshot_set(connection, case_id, row)
            comparison = compare_price_sets(refs, endpoint)
        except ContractError as error:
            if 'price units' in str(error) or 'price-unit' in str(error):
                return None
            continue
        current = endpoint['case']
        return {'price': float(current['price']), 'price_date': current['price_date'],
                'currency': current['currency'], 'provider': current['provider'],
                'reference_price': refs['case']['price'], 'reference_date': refs['case']['price_date'],
                'reference_currency': refs['case']['currency'],
                'days': (date.fromisoformat(current['price_date']) - date.fromisoformat(refs['case']['price_date'])).days,
                'relative_spy_pp': comparison['relative_to_spy_pp'],
                'relative_sector_pp': comparison['relative_to_sector_pp'],
                'return_basis': comparison['return_basis']}
    return None
