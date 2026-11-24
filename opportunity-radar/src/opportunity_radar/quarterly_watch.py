from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from .db import RadarDB
from .transitions import ContractError

WATCH_OUTCOMES = {"KEEP_WATCH", "CONDITION_MET", "RECHECK_REQUIRED", "THESIS_BROKEN", "NO_DECISION"}
CANDIDATE_OUTCOMES = {"WATCH_PROPOSAL", "DECISION_READY", "NOT_WATCH"}
READY_OUTCOMES = {"KEEP_READY", "RECHECK_REQUIRED", "THESIS_BROKEN", "NO_DECISION"}


def quarter_key(day: date | None = None) -> str:
    current = day or date.today()
    quarter = (current.month - 1) // 3 + 1
    return f"{current.year}-Q{quarter}"


def _latest_case_rows(radar: RadarDB) -> list[dict[str, Any]]:
    with radar.connect() as connection:
        rows = connection.execute(
            """SELECT c.id,c.symbol,c.name,c.status,r.id review_id,r.version,
                      r.payload_json,r.created_at review_created_at,
                      (SELECT reason FROM transitions t WHERE t.case_id=c.id ORDER BY t.id DESC LIMIT 1) transition_reason
               FROM cases c
               JOIN reviews r ON r.id=(
                   SELECT r2.id FROM reviews r2
                   WHERE r2.case_id=c.id ORDER BY r2.version DESC LIMIT 1
               )
               WHERE c.status IN ('WATCH','READY')
               ORDER BY c.symbol"""
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["review"] = json.loads(str(item.pop("payload_json")))
            item["open_conditions"] = [
                dict(condition)
                for condition in connection.execute(
                    """SELECT kind,description,status,created_at
                       FROM watch_conditions
                       WHERE case_id=? AND status='OPEN' ORDER BY id""",
                    (row["id"],),
                ).fetchall()
            ]
            item["sources"] = [
                str(source["url"])
                for source in connection.execute(
                    "SELECT url FROM sources WHERE review_id=? ORDER BY id",
                    (row["review_id"],),
                ).fetchall()
            ]
            reference = connection.execute(
                """SELECT m.symbol,m.price,m.price_date,m.currency,m.provider,m.semantics
                   FROM shadow_entries s JOIN market_snapshots m ON m.id=s.case_snapshot_id
                   WHERE s.case_id=?""", (row["id"],),
            ).fetchone()
            item["reference"] = dict(reference) if reference is not None else None
            if item["status"] == "READY":
                item["position_link"] = "UNCONFIRMED"
            result.append(item)
        return result


def _awaiting_candidate_rows(radar: RadarDB) -> list[dict[str, Any]]:
    with radar.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                """SELECT ci.id candidate_id,ci.stable_identity,d.signal_date,
                          ci.symbol,ci.name,d.reason,d.reader_text,
                          d.report_path,d.created_at
                   FROM candidate_decisions d
                   JOIN candidate_inbox ci
                     ON ci.stable_identity=d.stable_identity AND ci.status='OPEN'
                   WHERE d.id=(
                       SELECT MAX(d2.id) FROM candidate_decisions d2
                       WHERE d2.stable_identity=d.stable_identity
                   )
                     AND d.decision='AWAITING_USER'
                     AND d.signal_date=json_extract(ci.metrics_json,'$.first_entry_month')
                   ORDER BY d.created_at,d.id"""
            ).fetchall()
        ]


def watch_letter_context(radar: RadarDB, period: str) -> dict[str, Any]:
    try:
        year_text, quarter_text = period.split("-Q")
        year = int(year_text)
        quarter = int(quarter_text)
    except (ValueError, TypeError) as error:
        raise ContractError("period must be YYYY-QN") from error
    if str(year) != year_text or quarter not in {1, 2, 3, 4} or period != f"{year}-Q{quarter}":
        raise ContractError("period must be YYYY-QN")
    cases = _latest_case_rows(radar)
    with radar.connect() as connection:
        active_positions = [dict(row) for row in connection.execute(
            "SELECT id,symbol,case_id,quantity FROM positions WHERE status='ACTIVE' ORDER BY id"
        )]
    held_case_ids = {item["case_id"] for item in active_positions if item["case_id"] is not None}
    awaiting_candidates = _awaiting_candidate_rows(radar)
    for item in awaiting_candidates:
        report = Path(str(item["report_path"] or ""))
        if not report.is_absolute():
            report = Path(__file__).resolve().parents[2] / report
        try:
            item["report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
        except OSError as error:
            raise ContractError(f"candidate report unavailable: {item['symbol']}") from error
    bound_payload = {
        "period": period,
        "watch_cases": [item for item in cases if item["status"] == "WATCH"],
        "ready_cases": [item for item in cases if item["status"] == "READY" and item["id"] not in held_case_ids],
        "active_positions": active_positions,
        "awaiting_candidates": awaiting_candidates,
    }
    context_digest = hashlib.sha256(
        json.dumps(
            bound_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return {**bound_payload, "context_digest": context_digest}


def _validate_outcomes(
    value: object,
    *,
    expected_symbols: list[str],
    allowed: set[str],
    field: str,
) -> None:
    if not isinstance(value, list):
        raise ContractError(f"{field} must be a list")
    symbols: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            raise ContractError(f"{field} entries must be objects")
        symbol = item.get("symbol")
        outcome = item.get("outcome")
        if not isinstance(symbol, str) or not symbol:
            raise ContractError(f"{field} entries require symbol")
        if outcome not in allowed:
            raise ContractError(f"{field} contains invalid outcome")
        symbols.append(symbol)
    if len(symbols) != len(set(symbols)):
        raise ContractError(f"{field} contains duplicate symbols")
    if symbols != expected_symbols:
        raise ContractError(f"{field} must cover the current symbols in order")


def _validate_candidate_outcomes(value: object, expected: list[dict[str, Any]]) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        raise ContractError("candidate_outcomes must cover the current candidates in order")
    for item, candidate in zip(value, expected):
        if not isinstance(item, dict):
            raise ContractError("candidate_outcomes entries must be objects")
        if type(item.get("candidate_id")) is not int or any(
            item.get(key) != candidate[key]
            for key in ("candidate_id", "stable_identity", "signal_date", "symbol")
        ):
            raise ContractError("candidate_outcomes must bind exact candidate_id, stable_identity, signal_date and symbol")
        if item.get("outcome") not in CANDIDATE_OUTCOMES:
            raise ContractError("candidate_outcomes contains invalid outcome")


def validate_watch_letter_manifest(
    radar: RadarDB, period: str, manifest: dict[str, object], *, body: str | None = None
) -> dict[str, object]:
    context = watch_letter_context(radar, period)
    if manifest.get("period") != period:
        raise ContractError("watch letter manifest period mismatch")
    if manifest.get("context_digest") != context["context_digest"]:
        raise ContractError("watch letter manifest context is stale")
    if body is not None and manifest.get("body_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest():
        raise ContractError("watch letter body does not match its reviewed manifest")
    for field, group, allowed in (
        ("watch_outcomes", "watch_cases", WATCH_OUTCOMES),
        ("ready_outcomes", "ready_cases", READY_OUTCOMES),
    ):
        _validate_outcomes(
            manifest.get(field), expected_symbols=[str(item["symbol"]) for item in context[group]],
            allowed=allowed, field=field,
        )
    _validate_candidate_outcomes(manifest.get("candidate_outcomes"), context["awaiting_candidates"])
    return context
