from __future__ import annotations

from datetime import date
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .transitions import ContractError

RECOMMENDATIONS = {"HOLD", "TRIM", "EXIT", "NO_DECISION"}
EVENT_ACTIONS = {"TRIM", "EXIT"}


def monthly_brief_context(radar: Any, period: str) -> dict[str, Any]:
    """Bind the current month's actual episodes, baselines, reviews and reports."""
    if not radar.monthly_position_review_status(period)["complete"]:
        raise ContractError("monthly position review is incomplete")
    positions = []
    with radar.connect() as connection:
        for row in connection.execute("SELECT * FROM positions WHERE status='ACTIVE' ORDER BY id").fetchall():
            position = dict(row)
            baseline = connection.execute(
                "SELECT * FROM position_baselines WHERE position_id=? ORDER BY version DESC LIMIT 1",
                (position["id"],),
            ).fetchone()
            review = connection.execute(
                """SELECT pr.* FROM position_reviews pr
                   WHERE position_id=? AND substr(review_date,1,7)=?
                     AND NOT EXISTS (SELECT 1 FROM position_reviews child WHERE child.supersedes_review_id=pr.id)""",
                (position["id"], period),
            ).fetchone()
            if baseline is None or review is None:
                raise ContractError("monthly brief needs a baseline and review for every active episode")
            baseline, review = dict(baseline), dict(review)
            if review.get("baseline_id") != baseline["id"]:
                raise ContractError("monthly review was written against an older baseline")
            report = Path(str(review["report_path"]))
            if not report.is_absolute():
                report = Path(__file__).resolve().parents[2] / report
            try:
                report_bytes = report.read_bytes()
            except OSError as error:
                raise ContractError(f"monthly report unavailable: {position['symbol']}") from error
            if not report_bytes.strip():
                raise ContractError("monthly report is empty")
            positions.append({"position": position, "baseline": baseline, "review": review,
                              "report_sha256": hashlib.sha256(report_bytes).hexdigest()})
    payload = {"period": period, "positions": positions}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**payload, "context_digest": digest}


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"position review requires {key}")
    return value.strip()


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractError(f"{key} must be text or null")
    return value.strip() or None


def _date(payload: dict[str, Any], key: str) -> str:
    value = _text(payload, key)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ContractError(f"{key} must be YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise ContractError(f"{key} must be YYYY-MM-DD")
    return value


def _optional_positive_number(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ContractError(f"{key} must be a positive number or null")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ContractError(f"{key} must be a positive number or null") from error
    if not math.isfinite(number) or number <= 0:
        raise ContractError(f"{key} must be a positive number or null")
    return number


def _identifier(payload: dict[str, Any], key: str, *, optional: bool = False) -> int | None:
    value = payload.get(key)
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractError(f"{key} must be a positive integer")
    return value


def validate_position_review(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError("position review input must be a JSON object")
    recommendation = _text(payload, "recommendation").upper()
    if recommendation not in RECOMMENDATIONS:
        raise ContractError("recommendation must be HOLD, TRIM, EXIT or NO_DECISION")
    missing_fact = _optional_text(payload, "missing_decision_fact")
    next_check_on = _optional_text(payload, "next_check_on")
    if recommendation == "NO_DECISION":
        if not missing_fact or not next_check_on:
            raise ContractError("NO_DECISION requires missing_decision_fact and next_check_on")
        next_check_on = _date({"next_check_on": next_check_on}, "next_check_on")
        if next_check_on <= _date(payload, "review_date"):
            raise ContractError("next_check_on must follow review_date")
    elif missing_fact or next_check_on:
        raise ContractError("only NO_DECISION accepts a missing fact and next check")
    return {
        "position_id": _identifier(payload, "position_id"),
        "baseline_id": _identifier(payload, "baseline_id"),
        "supersedes_review_id": _identifier(payload, "supersedes_review_id", optional=True),
        "correction_reason": _optional_text(payload, "correction_reason"),
        "review_date": _date(payload, "review_date"),
        "recommendation": recommendation,
        "summary": _text(payload, "summary"),
        "strongest_counterevidence": _text(payload, "strongest_counterevidence"),
        "report_path": _text(payload, "report_path"),
        "missing_decision_fact": missing_fact,
        "next_check_on": next_check_on,
        "reviewer": _text(payload, "reviewer"),
    }


def validate_position_event(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError("position event input must be a JSON object")
    action = _text(payload, "action").upper()
    if action not in EVENT_ACTIONS:
        raise ContractError("position event action must be TRIM or EXIT")
    quantity = _optional_positive_number(payload, "quantity")
    if action == "TRIM" and quantity is None:
        raise ContractError("TRIM requires quantity")
    if action == "EXIT" and quantity is not None:
        raise ContractError("EXIT always closes the full remaining quantity")
    return {
        "position_id": _identifier(payload, "position_id"),
        "execution_reference": _text(payload, "execution_reference"),
        "action": action,
        "event_date": _date(payload, "event_date"),
        "quantity": quantity,
        "price": _optional_positive_number(payload, "price"),
        "reason": _text(payload, "reason"),
    }
