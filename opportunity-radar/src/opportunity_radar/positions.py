from __future__ import annotations

from datetime import date
import math
from typing import Any

from .transitions import ContractError


def _required_text(payload: dict[str, Any], key: str) -> str:
    raw_value = payload.get(key)
    if not isinstance(raw_value, str):
        raise ContractError(f"position requires {key}")
    value = raw_value.strip()
    if not value:
        raise ContractError(f"position requires {key}")
    return value


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    raw_value = payload.get(key)
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ContractError(f"{key} must be text or null")
    return raw_value.strip() or None


def _strict_date_value(value: str, key: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ContractError(f"{key} must be YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise ContractError(f"{key} must be YYYY-MM-DD")
    return value


def _strict_date(payload: dict[str, Any], key: str) -> str:
    return _strict_date_value(_required_text(payload, key), key)


def _optional_date(payload: dict[str, Any], key: str) -> str | None:
    value = _optional_text(payload, key)
    return _strict_date_value(value, key) if value is not None else None


def _positive_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ContractError(f"{key} must be a positive number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ContractError(f"{key} must be a positive number") from error
    if not math.isfinite(number) or number <= 0:
        raise ContractError(f"{key} must be a positive number")
    return number


def validate_position_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError("position input must be a JSON object")

    kind = _required_text(payload, "kind").lower()
    if kind not in {"stock", "etf"}:
        raise ContractError("kind must be stock or etf")

    currency = _required_text(payload, "currency").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ContractError("currency must be a three-letter code")

    purchase_date = _optional_date(payload, "purchase_date")
    approximate = payload.get("purchase_date_is_approximate", False)
    if not isinstance(approximate, bool):
        raise ContractError("purchase_date_is_approximate must be true or false")
    if approximate and purchase_date is None:
        raise ContractError("an approximate purchase date still requires purchase_date")

    linked_case_symbol = _optional_text(payload, "linked_case_symbol")
    benchmark_symbol = _optional_text(payload, "benchmark_symbol")

    role = _optional_text(payload, "investment_role")
    if role not in {None, "opportunity", "core", "hedge"}:
        raise ContractError("investment_role must be opportunity, core, hedge or null")
    frame = payload.get("investment_frame")
    from .review import validate_investment_frame
    validate_investment_frame(frame)
    if role == "opportunity" and frame is None:
        raise ContractError("new opportunity baseline requires investment_frame")
    if purchase_date and purchase_date > date.today().isoformat():
        raise ContractError("purchase_date cannot be in the future")
    return {
        "investment_role": role,
        "investment_frame": frame,
        "symbol": _required_text(payload, "symbol").upper(),
        "name": _required_text(payload, "name"),
        "kind": kind,
        "currency": currency,
        "linked_case_symbol": linked_case_symbol.upper() if linked_case_symbol else None,
        "purchase_date": purchase_date,
        "purchase_date_is_approximate": approximate,
        "average_price": _positive_number(payload, "average_price"),
        "quantity": _positive_number(payload, "quantity"),
        "invested_amount": _positive_number(payload, "invested_amount"),
        "objective": _required_text(payload, "objective"),
        "horizon": _required_text(payload, "horizon"),
        "exit_strategy": _required_text(payload, "exit_strategy"),
        "benchmark_symbol": benchmark_symbol.upper() if benchmark_symbol else None,
        "baseline_as_of": _strict_date(payload, "baseline_as_of"),
        "provenance": _required_text(payload, "provenance"),
    }
