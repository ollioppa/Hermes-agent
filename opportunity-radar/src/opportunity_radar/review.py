from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .transitions import ContractError

COMMON_FIELDS = {
    "evidence_as_of",
    "motor",
    "environment",
    "relative_strength",
    "expectation",
    "asymmetry",
    "counterpath",
    "falsifier",
    "missing_to_ready",
}
STOCK_FIELDS = {
    "moat_competition",
    "cash_conversion",
    "balance_financing",
    "capital_allocation",
    "valuation",
    "margins",
    "dilution",
    "customer_economics",
}
ETF_FIELDS = {
    "index_methodology",
    "holdings_transmission",
    "concentration",
    "costs_liquidity",
    "rebalancing",
    "overlap",
}

CUSTOMER_ECONOMICS_FIELDS = {
    "historical_path",
    "growth_composition",
    "customer_value",
    "support_intensity",
    "margin_source_and_use",
    "rent_quality",
    "normalization_test",
}


def validate_investment_frame(value: object) -> None:
    """Validate a supplied forecast frame; old unknown frames remain unknown."""
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise ContractError("investment_frame must be an object")
    try:
        start = date.fromisoformat(str(value["horizon_start_date"]))
        end = date.fromisoformat(str(value["horizon_end_date"]))
    except (KeyError, ValueError) as error:
        raise ContractError("investment_frame requires ISO start/end dates") from error
    if start.isoformat() != value["horizon_start_date"] or end.isoformat() != value["horizon_end_date"]:
        raise ContractError("investment_frame dates must be canonical YYYY-MM-DD")
    if end <= start or (end.year, end.month, end.day) > (start.year + 5, start.month, start.day):
        raise ContractError("investment_frame needs a future endpoint within five years of its original start")
    if value.get("comparison_currency") != "EUR" or not isinstance(value.get("report_path"), str) or not value["report_path"].strip():
        raise ContractError("investment_frame requires EUR comparison and a full report path")


def validate_review(kind: str, payload: Mapping[str, object]) -> None:
    validate_investment_frame(payload.get("investment_frame"))
    missing_common = sorted(field for field in COMMON_FIELDS if not payload.get(field))
    if missing_common:
        raise ContractError("review missing common fields: " + ", ".join(missing_common))
    try:
        date.fromisoformat(str(payload["evidence_as_of"]))
    except ValueError as exc:
        raise ContractError("evidence_as_of must be an ISO date") from exc
    specific = STOCK_FIELDS if kind == "stock" else ETF_FIELDS
    missing_specific = sorted(field for field in specific if not payload.get(field))
    if missing_specific:
        label = "stock" if kind == "stock" else "ETF"
        raise ContractError(f"{label} review missing fields: " + ", ".join(missing_specific))
    if kind == "stock":
        customer_economics = payload["customer_economics"]
        if not isinstance(customer_economics, Mapping):
            raise ContractError("stock review customer_economics must be a mapping")
        missing_customer_economics = sorted(
            field
            for field in CUSTOMER_ECONOMICS_FIELDS
            if not isinstance(customer_economics.get(field), str)
            or not str(customer_economics[field]).strip()
        )
        if missing_customer_economics:
            raise ContractError(
                "stock review customer_economics missing fields: "
                + ", ".join(missing_customer_economics)
            )
