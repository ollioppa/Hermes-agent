from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.evaluate import evaluate_outcomes, evaluate_pre_ready_timing
from opportunity_radar.models import MarketSnapshot


REVIEW = {
    "evidence_as_of": "2026-07-16",
    "motor": "specific motor", "environment": "named regime", "relative_strength": "relative evidence",
    "expectation": "priced expectation", "asymmetry": "base upside downside", "counterpath": "market right",
    "falsifier": "specific failure", "missing_to_ready": "earnings", "moat_competition": "evidence",
    "cash_conversion": "evidence", "balance_financing": "evidence", "capital_allocation": "evidence",
    "valuation": "anchor",
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


def snap(symbol: str, role: str, price: float, date: str) -> MarketSnapshot:
    return MarketSnapshot(symbol, role, price, date, date + "T22:00:00Z", "USD", "test", 'price return only |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}')


def test_price_comparison_suspends_unit_breaks_or_missing_coverage() -> None:
    from opportunity_radar.market import compare_price_sets
    from opportunity_radar.transitions import ContractError
    start = {key: snap(symbol, role, 100, "2026-09-01").__dict__ for key, symbol, role in
             (("case", "UNH", "case"), ("spy", "SPY", "benchmark"), ("sector", "XLV", "sector"))}
    end = {key: {**row, "price_date": "2026-10-01", "price": 50} for key, row in start.items()}
    assert compare_price_sets(start, end)["case_return_pct"] == -50
    for semantics in (end["case"]["semantics"].split(" |units=")[0],
                      end["case"]["semantics"].replace('"breaks":[]', '"breaks":["2026-09-15"]')):
        with pytest.raises(ContractError, match="price units unresolved"):
            compare_price_sets(start, {**end, "case": {**end["case"], "semantics": semantics}})
    split_semantics = end["case"]["semantics"].replace('"breaks":[]', '"breaks":["2026-09-15"]')
    same_day = {key: {**row, "price_date": "2026-09-01"} for key, row in end.items()}
    with pytest.raises(ContractError, match="price units unresolved"):
        compare_price_sets(start, {**same_day, "case": {**same_day["case"], "semantics": split_semantics}})
    known_start = {**start, "case": {**start["case"], "semantics": split_semantics}}
    with pytest.raises(ContractError, match="price units unresolved"):
        compare_price_sets(known_start, end)
    assert compare_price_sets(known_start, known_start)["case_return_pct"] == 0


def test_timing_evaluation_exposes_confirmation_tax_against_shadow_entry(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    initial = {
        "case": radar.record_snapshot(case_id, snap("UNH", "case", 400.84, "2026-09-01")),
        "spy": radar.record_snapshot(case_id, snap("SPY", "benchmark", 765.96, "2026-09-01")),
        "sector": radar.record_snapshot(case_id, snap("XLV", "sector", 167.13, "2026-09-01")),
    }
    radar.freeze_review(case_id, REVIEW, source_urls=["https://example.com"], snapshot_ids=initial, immediate_investable=True)
    condition = radar.add_watch_condition(case_id, "event", "earnings confirm motor")
    radar.transition(case_id, "WATCH", "wait for earnings")
    radar.mark_ready(
        case_id,
        condition,
        condition_evidence="earnings confirmed",
        reason="condition met",
        case_snapshot=snap("UNH", "ready", 410.0, "2026-10-01"),
        spy_snapshot=snap("SPY", "benchmark", 770.0, "2026-10-01"),
        sector_snapshot=snap("XLV", "sector", 168.0, "2026-10-01"),
    )

    result = evaluate_pre_ready_timing(radar, case_id)

    assert result["case_return_pct"] == pytest.approx(2.2852, abs=0.001)
    assert result["spy_return_pct"] == pytest.approx(0.5274, abs=0.001)
    assert result["relative_move_pp"] == pytest.approx(1.7578, abs=0.001)
    assert result["sector_return_pct"] == pytest.approx(0.5206, abs=0.001)
    assert result["relative_to_sector_pp"] == pytest.approx(1.7646, abs=0.001)
    assert result["reading"] == "waiting paid a confirmation tax"

    # A later foreign same-date benchmark must not rewrite the bound READY set.
    radar.record_snapshot(case_id, MarketSnapshot("SPY", "benchmark", 1.0, "2026-10-01",
        "2026-10-01T23:00:00Z", "EUR", "unrelated", "different units"))
    assert evaluate_pre_ready_timing(radar, case_id) == result

    radar.record_outcome(
        case_id,
        snap("UNH", "outcome", 450.0, "2027-09-01"),
        snap("SPY", "benchmark", 800.0, "2027-09-01"),
        snap("XLV", "sector", 170.0, "2027-09-01"),
    )
    outcomes = evaluate_outcomes(radar)

    assert outcomes[0]["kind"] == "stock"
    assert outcomes[0]["decision_status"] == "READY"
    assert outcomes[0]["shadow_date"] == "2026-09-01"
    days = outcomes[0]["observation_days"]
    assert isinstance(days, int) and days > 0
    from opportunity_radar.market import latest_market_metrics
    with radar.connect() as connection:
        latest = latest_market_metrics(connection, case_id)
        assert latest is not None and latest["price_date"] == "2027-09-01"
    assert outcomes[0]["relative_to_spy_pp"] == pytest.approx(
        outcomes[0]["case_return_pct"] - outcomes[0]["spy_return_pct"]
    )
