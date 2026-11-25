import sqlite3
from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.transitions import ContractError


@pytest.mark.parametrize("stamp", ["2026-10-24T08:07:33Z", "2026-10-24T08:07:33+00:00", "2026-10-24T10:07:33+02:00"])
def test_snapshot_accepts_aware_timestamps_without_rewriting_input(stamp):
    item = MarketSnapshot("TEST", "case", 1.0, "2026-10-24", stamp, "USD", "fixture", "price")
    assert item.retrieved_at == stamp


@pytest.mark.parametrize("stamp", ["2026-10-24T08:07:33", "2026-10-24", "not-a-date", "2026-10-24Z08:07:33", None, 123])
def test_snapshot_rejects_missing_timezone_or_invalid_timestamp(stamp):
    with pytest.raises(ContractError, match="timezone-aware"):
        MarketSnapshot("TEST", "case", 1.0, "2026-10-24", stamp, "USD", "fixture", "price")


STOCK_REVIEW = {
    "evidence_as_of": "2026-07-16",
    "motor": "operative normalization",
    "environment": "healthcare demand and regulation",
    "relative_strength": "revenue holds better than peers",
    "expectation": "persistent margin damage is priced",
    "asymmetry": "base, upside and permanent-loss path documented",
    "counterpath": "cost pressure persists",
    "falsifier": "two quarters without margin stabilization",
    "missing_to_ready": "Q3 margin confirmation",
    "moat_competition": "scaled payer and services network",
    "cash_conversion": "cash conversion must recover",
    "balance_financing": "investment grade funding remains available",
    "capital_allocation": "buybacks paused if balance sheet weakens",
    "valuation": "base and downside values compared with SPY opportunity cost",
    "margins": "operating margin path documented",
    "dilution": "share count and dilution path documented",
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


def snapshot(symbol: str, role: str, price: float) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        role=role,
        price=price,
        price_date="2026-09-08",
        retrieved_at="2026-09-09T05:00:00Z",
        currency="USD",
        provider="nasdaq_info",
        semantics="last sale price; not total return",
    )


def test_first_review_freezes_shadow_entry_and_later_review_cannot_replace_it(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    case_quote = radar.record_snapshot(case_id, snapshot("UNH", "case", 400.84))
    spy_quote = radar.record_snapshot(case_id, snapshot("SPY", "benchmark", 765.96))
    sector_quote = radar.record_snapshot(case_id, snapshot("XLV", "sector", 167.13))

    review_id = radar.freeze_review(
        case_id,
        STOCK_REVIEW,
        source_urls=["https://example.invalid/fixture-source"],
        snapshot_ids={"case": case_quote, "spy": spy_quote, "sector": sector_quote},
        immediate_investable=False,
    )
    first = radar.get_shadow_entry(case_id)

    changed = dict(STOCK_REVIEW, missing_to_ready="Q4 margin confirmation")
    radar.freeze_review(case_id, changed)

    assert first == {
        "review_id": review_id,
        "case_price": 400.84,
        "spy_price": 765.96,
        "sector_price": 167.13,
        "price_date": "2026-09-08",
        "immediate_investable": False,
    }
    assert radar.get_shadow_entry(case_id) == first

    with radar.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE reviews SET payload_json = '{}' WHERE id = ?", (review_id,))
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE shadow_entries SET immediate_investable = 1 WHERE case_id = ?", (case_id,))
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE market_snapshots SET price = 1 WHERE id = ?", (case_quote,))


def test_first_review_binds_case_spy_sector_and_one_price_date(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    ids = {
        "case": radar.record_snapshot(case_id, snapshot("WRONG", "case", 400.84)),
        "spy": radar.record_snapshot(case_id, snapshot("QQQ", "benchmark", 765.96)),
        "sector": radar.record_snapshot(case_id, MarketSnapshot("XLE", "sector", 167.13, "2026-09-07", "2026-09-09T05:00:00Z", "USD", "nasdaq_info", "last sale")),
    }

    with pytest.raises(ContractError, match="snapshot binding"):
        radar.freeze_review(case_id, STOCK_REVIEW, source_urls=["https://example.com"], snapshot_ids=ids, immediate_investable=False)
