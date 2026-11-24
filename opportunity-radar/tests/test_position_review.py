import sqlite3
from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.transitions import ContractError


def position_payload(symbol: str = "AAA") -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": f"{symbol} position",
        "kind": "stock",
        "currency": "EUR",
        "linked_case_symbol": None,
        "purchase_date": None,
        "purchase_date_is_approximate": False,
        "average_price": 100.0,
        "quantity": 10.0,
        "invested_amount": 1000.0,
        "objective": "Own the stated equity thesis",
        "horizon": "three years",
        "exit_strategy": "Exit if the thesis breaks",
        "benchmark_symbol": None,
        "baseline_as_of": "2026-09-23",
        "provenance": "test fixture",
    }


def review_payload(
    recommendation: str = "HOLD", review_date: str = "2026-09-23"
) -> dict[str, object]:
    return {
        "review_date": review_date,
        "position_id": 1,
        "baseline_id": 1,
        "recommendation": recommendation,
        "summary": "The baseline remains intact",
        "strongest_counterevidence": "Demand is weaker than expected",
        "report_path": f"output/position-reviews/{review_date}-AAA.md",
        "missing_decision_fact": None,
        "next_check_on": None,
        "reviewer": "monthly-position-review",
    }


def test_monthly_status_requires_every_active_position(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload("AAA"), confirmed_by="owner")
    radar.import_position(position_payload("BBB"), confirmed_by="owner")

    radar.record_position_review("AAA", review_payload(review_date="2026-10-02"))
    partial = radar.monthly_position_review_status("2026-10")
    assert partial["complete"] is False
    assert partial["reviewed_symbols"] == ["AAA"]
    assert partial["missing_symbols"] == ["BBB"]

    payload = review_payload(review_date="2026-10-03")
    payload["report_path"] = "output/position-reviews/2026-10-03-BBB.md"
    payload.update(position_id=2, baseline_id=2)
    radar.record_position_review("BBB", payload)
    complete = radar.monthly_position_review_status("2026-10")
    assert complete["complete"] is True
    assert complete["missing_symbols"] == []

    with pytest.raises(ContractError, match="YYYY-MM"):
        radar.monthly_position_review_status("2026-1")


def test_review_recommendation_never_changes_holding(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")
    payload = review_payload("EXIT")

    radar.record_position_review("AAA", payload)
    result = radar.show_position("AAA")

    assert result["status"] == "ACTIVE"
    assert result["quantity"] == 10.0
    assert result["reviews"][0]["recommendation"] == "EXIT"
    assert result["events"] == []


def test_no_decision_requires_one_missing_fact_and_next_check(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")
    payload = review_payload("NO_DECISION")

    with pytest.raises(ContractError, match="requires missing_decision_fact"):
        radar.record_position_review("AAA", payload)

    payload["missing_decision_fact"] = "Current fund holdings are unavailable"
    payload["next_check_on"] = "2026-10-01"
    radar.record_position_review("AAA", payload)
    assert radar.show_position("AAA")["reviews"][0]["next_check_on"] == "2026-10-01"



def test_position_event_requires_owner_and_trim_changes_only_quantity(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")
    event = {
        "position_id": 1,
        "execution_reference": "fixture-execution",
        "action": "TRIM",
        "event_date": "2026-09-24",
        "quantity": 2.5,
        "price": 120.0,
        "reason": "Executed partial sale",
    }

    for invalid_actor in ("agent", "Owner", "OWNER", " owner "):
        with pytest.raises(ContractError, match="confirmed-by owner"):
            radar.confirm_position_event("AAA", event, confirmed_by=invalid_actor)
    radar.confirm_position_event("AAA", event, confirmed_by="owner")
    result = radar.show_position("AAA")

    assert result["status"] == "ACTIVE"
    assert result["quantity"] == 7.5
    assert result["events"][0]["quantity_before"] == 10.0
    assert result["events"][0]["quantity_after"] == 7.5
    assert result["events"][0]["confirmed_by"] == "owner"


def test_invalid_trim_rolls_back_without_event(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")
    event = {
        "position_id": 1,
        "execution_reference": "fixture-execution",
        "action": "TRIM",
        "event_date": "2026-09-24",
        "quantity": 10,
        "price": None,
        "reason": "Invalid full trim",
    }

    with pytest.raises(ContractError, match="less than"):
        radar.confirm_position_event("AAA", event, confirmed_by="owner")
    result = radar.show_position("AAA")
    assert result["quantity"] == 10.0
    assert result["events"] == []


def test_confirmed_exit_closes_position_and_preserves_quantity_history(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")
    event = {
        "position_id": 1,
        "execution_reference": "fixture-execution",
        "action": "EXIT",
        "event_date": "2026-09-24",
        "quantity": None,
        "price": 130.0,
        "reason": "Executed full sale",
    }

    radar.confirm_position_event("AAA", event, confirmed_by="owner")
    result = radar.show_position("AAA")

    assert result["status"] == "CLOSED"
    assert result["quantity"] == 0.0
    assert result["closed_at"] == "2026-09-24"
    assert result["events"][0]["quantity_after"] == 0.0
    assert radar.list_positions()[0]["quantity"] == 0.0



def test_reviews_and_events_are_append_only(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")
    radar.record_position_review("AAA", review_payload())
    radar.confirm_position_event(
        "AAA",
        {
            "action": "TRIM",
            "position_id": 1,
            "execution_reference": "fixture-execution",
            "event_date": "2026-09-24",
            "quantity": 1,
            "price": None,
            "reason": "Executed trim",
        },
        confirmed_by="owner",
    )

    with radar.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE position_reviews SET summary='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM position_reviews")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE position_events SET reason='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM position_events")


def test_baseline_review_and_trade_successors_preserve_episode_identity(tmp_path: Path) -> None:
    from opportunity_radar.position_review import monthly_brief_context
    radar = RadarDB(tmp_path / "lifecycle.sqlite3")
    radar.initialize()
    position_id = radar.import_position(position_payload(), confirmed_by="owner")
    baselines = radar.show_position("AAA")["baselines"]
    assert isinstance(baselines, list)
    baseline_id = int(str(baselines[0]["id"]))
    report = tmp_path / "review.md"
    report.write_text("# Explicit monthly fixture\nRemaining chance reviewed.")
    first = {**review_payload(), "position_id": position_id, "baseline_id": baseline_id,
             "report_path": str(report)}
    first_id = radar.record_position_review("AAA", first)
    before = monthly_brief_context(radar, "2026-09")
    with pytest.raises(ContractError, match="monthly correction"):
        radar.record_position_review("AAA", first)
    successor = radar.revise_position_baseline("AAA", {
        "position_id": position_id, "predecessor_baseline_id": baseline_id,
        "effective_on": "2026-09-24", "change_reason": "Confirmed strategy clarification",
        "baseline": {"objective": "Revised remaining opportunity"}}, confirmed_by="owner")
    assert radar.monthly_position_review_status("2026-09")["complete"] is False
    correction = {**first, "review_date": "2026-09-24", "baseline_id": successor,
                  "supersedes_review_id": first_id, "correction_reason": "New baseline reviewed"}
    radar.record_position_review("AAA", correction)
    assert monthly_brief_context(radar, "2026-09")["context_digest"] != before["context_digest"]
    report.write_text("# Changed report bytes")
    changed = monthly_brief_context(radar, "2026-09")
    trim = {"position_id": position_id, "execution_reference": "broker-trim-1", "action": "TRIM",
            "event_date": "2026-09-24", "quantity": 1, "price": None, "reason": "Confirmed fixture trade"}
    trim_id = radar.confirm_position_event("AAA", trim, confirmed_by="owner")
    assert radar.confirm_position_event("AAA", trim, confirmed_by="owner") == trim_id
    assert monthly_brief_context(radar, "2026-09")["context_digest"] != changed["context_digest"]
    exit_event = {**trim, "execution_reference": "broker-exit-1", "action": "EXIT",
                  "quantity": None, "event_date": "2026-09-25"}
    exit_id = radar.confirm_position_event("AAA", exit_event, confirmed_by="owner")
    radar.import_position(position_payload(), confirmed_by="owner")
    assert radar.confirm_position_event("AAA", exit_event, confirmed_by="owner") == exit_id
    assert radar.show_position("AAA")["quantity"] == 10
    with pytest.raises(ContractError, match="conflicting payload"):
        radar.confirm_position_event("AAA", {**exit_event, "price": 200}, confirmed_by="owner")
    new_id = int(str(radar.show_position("AAA")["id"]))
    for day in ("2026-09-22", "2026-09-23"):
        with pytest.raises(ContractError, match="confirmed holdings snapshot"):
            radar.confirm_position_event("AAA", {**trim, "position_id": new_id,
                "execution_reference": "backdated", "event_date": day}, confirmed_by="owner")
