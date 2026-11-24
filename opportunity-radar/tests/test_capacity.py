from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.transitions import ContractError


REVIEW = {
    "evidence_as_of": "2026-07-16",
    "motor": "specific internal growth motor",
    "environment": "named end-market regime",
    "relative_strength": "better than named peers",
    "expectation": "market prices a weaker path",
    "asymmetry": "base, upside and permanent-loss path",
    "counterpath": "the market is right",
    "falsifier": "named operating failure",
    "missing_to_ready": "named event",
    "moat_competition": "competitive evidence",
    "cash_conversion": "cash evidence",
    "balance_financing": "financing evidence",
    "capital_allocation": "allocation evidence",
    "valuation": "valuation anchor",
    "margins": "margin path",
    "dilution": "share-count path",
    "customer_economics": {
        "historical_path": "dated phases tested; masking remains open",
        "growth_composition": "price, volume, share and mix separated",
        "customer_value": "price compared with customer utility and peers",
        "support_intensity": "promotions and financing direction documented",
        "margin_source_and_use": "margin source and reinvestment documented",
        "rent_quality": "mixed evidence; no score or gate",
        "normalization_test": "existing falsifier tested under normal competition",
    },
}


def snap(symbol: str, role: str, price: float) -> MarketSnapshot:
    return MarketSnapshot(symbol, role, price, "2026-09-08", "2026-09-09T05:00:00Z", "USD", "test", "close")


def seed_watch(radar: RadarDB, symbol: str) -> int:
    case_id = radar.add_case(symbol, symbol, "stock", "XLV")
    ids = {
        "case": radar.record_snapshot(case_id, snap(symbol, "case", 100.0)),
        "spy": radar.record_snapshot(case_id, snap("SPY", "benchmark", 700.0)),
        "sector": radar.record_snapshot(case_id, snap("XLV", "sector", 160.0)),
    }
    radar.freeze_review(case_id, REVIEW, source_urls=["https://example.com/source"], snapshot_ids=ids, immediate_investable=False)
    radar.add_watch_condition(case_id, "event", "Next results confirm the motor")
    radar.transition(case_id, "WATCH", "review complete")
    return case_id


def test_only_eight_cases_may_be_active(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    for number in range(8):
        seed_watch(radar, f"T{number}")

    with pytest.raises(ContractError, match="active capacity"):
        seed_watch(radar, "T8")
