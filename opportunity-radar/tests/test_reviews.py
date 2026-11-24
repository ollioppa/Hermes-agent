from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.review import validate_review, validate_investment_frame
from opportunity_radar.transitions import ContractError


COMMON = {
    "evidence_as_of": "2026-07-16",
    "motor": "operative normalization",
    "environment": "healthcare demand and regulation",
    "relative_strength": "revenue holds better than peers",
    "expectation": "persistent margin damage is priced",
    "asymmetry": "base, upside and permanent-loss path documented",
    "counterpath": "cost pressure persists",
    "falsifier": "two quarters without margin stabilization",
    "missing_to_ready": "Q3 margin confirmation",
}


def test_optional_forecast_frame_keeps_history_unknown_and_rejects_false_dates() -> None:
    validate_investment_frame(None)
    frame = {"horizon_start_date": "2026-09-08", "horizon_end_date": "2029-09-08",
             "comparison_currency": "EUR", "report_path": "output/reviews/example.md"}
    validate_investment_frame(frame)
    for change in ({"horizon_end_date": "2025-09-08"}, {"horizon_start_date": "20260908"},
                   {"horizon_end_date": "2032-09-08"}, {"comparison_currency": "USD"}, {"report_path": None}):
        with pytest.raises(ContractError):
            validate_investment_frame({**frame, **change})


def test_stock_and_etf_reviews_have_distinct_required_evidence(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    stock = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    etf = radar.add_case("URA", "Global X Uranium ETF", "etf", "XLE")

    with pytest.raises(ContractError, match="stock review missing"):
        radar.freeze_review(stock, COMMON)

    with pytest.raises(ContractError, match="ETF review missing"):
        radar.freeze_review(etf, COMMON)


def test_new_stock_review_requires_complete_customer_economics() -> None:
    stock_review = {
        **COMMON,
        "moat_competition": "competition evidence",
        "cash_conversion": "cash evidence",
        "balance_financing": "financing evidence",
        "capital_allocation": "allocation evidence",
        "valuation": "valuation anchor",
        "margins": "margin path",
        "dilution": "share-count path",
        "customer_economics": {
            "historical_path": "OPEN_NO_EVIDENCE: no comparable pre-regime disclosure",
            "growth_composition": "price, volume, share and mix separated",
            "customer_value": "price compared with customer utility and peers",
            "support_intensity": "promotions and financing direction documented",
            "margin_source_and_use": "margin source and reinvestment documented",
            "rent_quality": "mixed evidence; no score or gate",
            "normalization_test": "existing falsifier tested under normal competition",
        },
    }

    validate_review("stock", stock_review)
    del stock_review["customer_economics"]["margin_source_and_use"]

    with pytest.raises(ContractError, match="customer_economics missing fields: margin_source_and_use"):
        validate_review("stock", stock_review)

    for invalid_value in ("   ", True, 42, {"text": "not a string"}):
        stock_review["customer_economics"]["margin_source_and_use"] = invalid_value
        with pytest.raises(
            ContractError,
            match="customer_economics missing fields: margin_source_and_use",
        ):
            validate_review("stock", stock_review)
