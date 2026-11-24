from __future__ import annotations

from datetime import date

from .db import RadarDB
from .market import bound_snapshots, compare_price_sets, snapshot_set
from .transitions import ContractError


def evaluate_pre_ready_timing(radar: RadarDB, case_id: int) -> dict[str, object]:
    with radar.connect() as connection:
        refs = bound_snapshots(connection, case_id)
        # Select the historical READY event, never today's same-date benchmark rows.
        ready = connection.execute(
            "SELECT id FROM market_snapshots WHERE case_id=? AND role='ready' ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        if ready is None:
            raise ContractError('timing evaluation requires a READY snapshot')
        binding = connection.execute(
            'SELECT * FROM ready_snapshot_sets WHERE case_id=? AND case_snapshot_id=?',
            (case_id, ready['id']),
        ).fetchone()
        if binding is None:
            raise ContractError('historical READY endpoint binding unresolved; no return calculated')
        endpoint = snapshot_set(connection, case_id, binding)
        comparison = compare_price_sets(refs, endpoint)
    relative = comparison['relative_to_spy_pp']
    reading = ('waiting paid a confirmation tax' if relative > 0 else
               'waiting avoided relative loss before READY' if relative < 0 else
               'waiting was neutral before READY')
    return {'case_id': case_id, 'shadow_date': refs['case']['price_date'],
            'ready_date': endpoint['case']['price_date'],
            'observation_days': (date.fromisoformat(endpoint['case']['price_date']) - date.fromisoformat(refs['case']['price_date'])).days, **comparison,
            'relative_move_pp': relative, 'reading': reading}


def evaluate_outcomes(radar: RadarDB) -> list[dict[str, object]]:
    result = []
    with radar.connect() as connection:
        rows = connection.execute(
            """SELECT oc.*,c.symbol,c.kind,m.price_date FROM outcome_checks oc
               JOIN cases c ON c.id=oc.case_id
               LEFT JOIN market_snapshots m ON m.id=oc.case_snapshot_id ORDER BY oc.id"""
        ).fetchall()
        for row in rows:
            item = {'outcome_id': row['id'], 'case_id': row['case_id'], 'symbol': row['symbol'],
                    'kind': row['kind'], 'decision_status': row['decision_status'],
                    'price_date': row['price_date'], 'shadow_date': None, 'observation_days': None}
            try:
                refs = bound_snapshots(connection, row['case_id'])
                endpoint = snapshot_set(connection, row['case_id'], row)
                if endpoint['case']['role'] != 'outcome':
                    raise ContractError('outcome endpoint has invalid role')
                item.update(compare_price_sets(refs, endpoint), evaluation_status='valid',
                            shadow_date=refs['case']['price_date'],
                            observation_days=(date.fromisoformat(endpoint['case']['price_date']) - date.fromisoformat(refs['case']['price_date'])).days)
            except ContractError as error:
                item.update(evaluation_status='unresolved', reason=str(error),
                            case_return_pct=None, spy_return_pct=None, sector_return_pct=None,
                            relative_to_spy_pp=None, relative_to_sector_pp=None,
                            return_basis='local instrument price return; no FX or dividends; not total return')
            result.append(item)
    return result
