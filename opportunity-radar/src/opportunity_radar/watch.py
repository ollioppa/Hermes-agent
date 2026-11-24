from __future__ import annotations

from .db import RadarDB
from .evaluate import evaluate_outcomes, evaluate_pre_ready_timing
from .market import NasdaqInfoProvider, YahooChartProvider, bound_snapshots, compare_price_sets
from .models import MarketSnapshot
from .transitions import ContractError


def fetch_bound_market_set(
    radar: RadarDB, symbol: str, *, case_role: str, provider: NasdaqInfoProvider | None = None,
) -> tuple[int, dict[str, MarketSnapshot]]:
    case = radar.get_case_by_symbol(symbol)
    case_id = int(str(case['id']))
    with radar.connect() as connection:
        refs = bound_snapshots(connection, case_id)
    if set(refs) != {'case', 'spy', 'sector'}:
        raise ContractError('market observation requires bound original snapshots')
    available = {}
    for key, role, kind in [('case', case_role, str(case['kind'])), ('spy', 'benchmark', 'etf'), ('sector', 'sector', 'etf')]:
        ref = refs[key]
        if provider is not None:
            quote = provider.fetch(ref['symbol'], kind, role)
            rows = {quote.price_date: quote}
        elif ref['quote_symbol']:
            source = YahooChartProvider(ref['quote_symbol'], ref['currency'], reference_date=ref['price_date'])
            rows = source.history(ref['symbol'], kind, role)
        elif ref['provider'] == 'nasdaq_info' and ref['currency'] == 'USD':
            quote = NasdaqInfoProvider(reference_date=ref['price_date']).fetch(ref['symbol'], kind, role)
            rows = {quote.price_date: quote}
        else:
            raise ContractError('unsupported bound market provider/currency')
        available[key] = rows
    common = set.intersection(*(set(rows) for rows in available.values()))
    if not common:
        raise ContractError('market snapshot set does not share one actual trade date')
    day = max(common)
    snapshots = {key: rows[day] for key, rows in available.items()}
    compare_price_sets(refs, {key: snapshot.__dict__ for key, snapshot in snapshots.items()})
    return case_id, snapshots


def observe_live(radar: RadarDB, symbol: str, provider: NasdaqInfoProvider | None = None) -> dict[str, object]:
    case_id, snapshots = fetch_bound_market_set(radar, symbol, case_role='case', provider=provider)
    ids = {}
    with radar.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        for key, snapshot in snapshots.items():
            cursor = connection.execute(
                """INSERT INTO market_snapshots(case_id,symbol,role,price,price_date,retrieved_at,currency,provider,semantics)
                   VALUES (:case_id,:symbol,:role,:price,:price_date,:retrieved_at,:currency,:provider,:semantics)""",
                dict(snapshot.__dict__, case_id=case_id),
            )
            assert cursor.lastrowid is not None
            ids[key] = cursor.lastrowid
    return {'case_id': case_id, 'price_date': snapshots['case'].price_date, 'snapshot_ids': ids}


def mark_ready_live(
    radar: RadarDB,
    symbol: str,
    *,
    condition_evidence: str,
    reason: str,
    provider: NasdaqInfoProvider | None = None,
) -> dict[str, object]:
    case = radar.get_case_by_symbol(symbol)
    if case["status"] != "WATCH":
        raise ContractError("ready-live requires a WATCH case")
    open_conditions = radar.get_open_conditions(int(case["id"]))
    if len(open_conditions) != 1:
        raise ContractError("ready-live requires exactly one open watch condition")
    case_id, snapshots = fetch_bound_market_set(radar, symbol, case_role="ready", provider=provider)
    radar.mark_ready(
        case_id,
        int(open_conditions[0]["id"]),
        condition_evidence=condition_evidence,
        reason=reason,
        case_snapshot=snapshots["case"],
        spy_snapshot=snapshots["spy"],
        sector_snapshot=snapshots["sector"],
    )
    return evaluate_pre_ready_timing(radar, case_id)


def record_outcome_live(
    radar: RadarDB, symbol: str, provider: NasdaqInfoProvider | None = None
) -> dict[str, object]:
    case_id, snapshots = fetch_bound_market_set(radar, symbol, case_role="outcome", provider=provider)
    outcome_id = radar.record_outcome(
        case_id, snapshots["case"], snapshots["spy"], snapshots["sector"]
    )
    row = next(item for item in evaluate_outcomes(radar) if item["outcome_id"] == outcome_id)
    return row
