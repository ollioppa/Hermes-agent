from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.transitions import ContractError


REVIEW = {
    "evidence_as_of": "2026-07-16",
    "motor": "specific motor",
    "environment": "named regime",
    "relative_strength": "relative evidence",
    "expectation": "priced expectation",
    "asymmetry": "base upside downside",
    "counterpath": "market is right",
    "falsifier": "specific failure",
    "missing_to_ready": "earnings confirmation",
    "moat_competition": "competition evidence",
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
    return MarketSnapshot(symbol, role, price, "2026-09-08", "2026-09-09T05:00:00Z", "USD", "test", 'close |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}')


def reviewed_case(radar: RadarDB) -> tuple[int, int]:
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    ids = {
        "case": radar.record_snapshot(case_id, snap("UNH", "case", 400.84)),
        "spy": radar.record_snapshot(case_id, snap("SPY", "benchmark", 765.96)),
        "sector": radar.record_snapshot(case_id, snap("XLV", "sector", 167.13)),
    }
    radar.freeze_review(case_id, REVIEW, source_urls=["https://example.com"], snapshot_ids=ids, immediate_investable=False)
    condition_id = radar.add_watch_condition(case_id, "event", "Q3 confirms margin recovery")
    return case_id, condition_id


def test_watch_requires_frozen_review_and_open_condition(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")

    with pytest.raises(ContractError, match="frozen review"):
        radar.transition(case_id, "WATCH", "interesting")


def test_ready_is_one_atomic_condition_and_snapshot_transition(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id, condition_id = reviewed_case(radar)
    radar.transition(case_id, "WATCH", "review complete")
    radar.record_snapshot(case_id, snap("UNH", "ready", 405.0))
    radar.record_snapshot(case_id, snap("SPY", "benchmark", 768.0))
    radar.record_snapshot(case_id, snap("XLV", "sector", 167.5))

    with pytest.raises(ContractError, match="atomic mark_ready"):
        radar.transition(case_id, "READY", "condition fulfilled")

    radar.mark_ready(
        case_id,
        condition_id,
        condition_evidence="Q3 margin recovered",
        reason="Q3 confirmed the motor",
        case_snapshot=snap("UNH", "ready", 410.0),
        spy_snapshot=snap("SPY", "benchmark", 770.0),
        sector_snapshot=snap("XLV", "sector", 168.0),
    )

    assert radar.get_case(case_id)["status"] == "READY"


def test_inbox_cannot_jump_directly_to_ready(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    ids = {
        "case": radar.record_snapshot(case_id, snap("UNH", "case", 400.84)),
        "spy": radar.record_snapshot(case_id, snap("SPY", "benchmark", 765.96)),
        "sector": radar.record_snapshot(case_id, snap("XLV", "sector", 167.13)),
    }
    radar.freeze_review(case_id, REVIEW, source_urls=["https://example.com"], snapshot_ids=ids, immediate_investable=True)

    with pytest.raises(ContractError, match="atomic mark_ready"):
        radar.transition(case_id, "READY", "looks good")
