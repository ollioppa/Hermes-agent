import json
import hashlib
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.quarterly_watch import (
    quarter_key,
    validate_watch_letter_manifest,
    watch_letter_context,
)
from opportunity_radar.transitions import ContractError


REVIEW: dict[str, object] = {
    "evidence_as_of": "2026-09-01",
    "motor": "Test motor",
    "environment": "Test environment",
    "relative_strength": "Test relative strength",
    "expectation": "Test expectation",
    "asymmetry": "Test asymmetry",
    "counterpath": "Test counterpath",
    "falsifier": "Two reports break the thesis",
    "missing_to_ready": "Next report confirms the condition",
    "moat_competition": "Test moat",
    "cash_conversion": "Test cash conversion",
    "balance_financing": "Test financing",
    "capital_allocation": "Test allocation",
    "valuation": "Test valuation",
    "margins": "Test margins",
    "dilution": "Test dilution",
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


def snap(symbol: str, role: str) -> MarketSnapshot:
    return MarketSnapshot(
        symbol, role, 100.0, "2026-09-01", "2026-09-02T00:00:00Z",
        "USD", "test", "close",
    )


def seeded_radar(path: Path) -> RadarDB:
    radar = RadarDB(path)
    radar.initialize()
    case_id = radar.add_case("AAA", "AAA Corp", "stock", "XLK")
    ids = {
        "case": radar.record_snapshot(case_id, snap("AAA", "case")),
        "spy": radar.record_snapshot(case_id, snap("SPY", "benchmark")),
        "sector": radar.record_snapshot(case_id, snap("XLK", "sector")),
    }
    radar.freeze_review(
        case_id,
        REVIEW,
        source_urls=["https://example.com/aaa"],
        snapshot_ids=ids,
        immediate_investable=False,
    )
    radar.add_watch_condition(case_id, "operating", "Next report confirms condition")
    radar.transition(case_id, "WATCH", "Owner confirmed WATCH")

    with radar.connect() as connection:
        cycle_id = connection.execute(
            """INSERT INTO screen_cycles(
                   cycle_key,cohort_index,provider,status,as_of,completed_at
               ) VALUES ('test:2026-Q3',0,'test','COMPLETED','2026-09-01',CURRENT_TIMESTAMP)"""
        ).lastrowid
        connection.execute(
            """INSERT INTO candidate_inbox(
                   stable_identity,symbol,name,kind,region,mic,status,
                   first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json
               ) VALUES (?,?,?,?,?,?,'OPEN',?,?,?,?)""",
            (
                "US:BBB", "BBB", "BBB Corp", "stock", "US", "US",
                cycle_id, cycle_id, "TREND_NORMALIZATION",
                json.dumps({"first_entry_month": "2026-08"}),
            ),
        )
    report = path.parent / "BBB.md"
    report.write_text("BBB completed fixture research", encoding="utf-8")
    radar.record_candidate_decision(
        "BBB",
        "AWAITING_USER",
        "Completed research needs Owner's decision",
        report_path=str(report),
        reader_text="BBB is fully researched.",
        decided_by="autonomous-candidate-research",
    )
    return radar


def test_quarter_key_is_calendar_quarter() -> None:
    assert quarter_key(date(2026, 1, 1)) == "2026-Q1"
    assert quarter_key(date(2026, 9, 30)) == "2026-Q3"
    assert quarter_key(date(2026, 12, 31)) == "2026-Q4"


def test_context_contains_only_watch_and_awaiting_user(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    context = watch_letter_context(radar, "2026-Q3")
    watch_cases = cast(list[dict[str, Any]], context["watch_cases"])
    candidates = cast(list[dict[str, Any]], context["awaiting_candidates"])

    assert [item["symbol"] for item in watch_cases] == ["AAA"]
    assert watch_cases[0]["open_conditions"][0]["description"] == (
        "Next report confirms condition"
    )
    assert [item["symbol"] for item in candidates] == ["BBB"]


def candidate_outcomes(context, outcome="NOT_WATCH"):
    return [{**{key: row[key] for key in ("candidate_id", "stable_identity", "signal_date", "symbol")},
             "outcome": outcome} for row in context["awaiting_candidates"]]


def test_manifest_must_cover_every_bound_symbol_once(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    context = watch_letter_context(radar, "2026-Q3")
    manifest = {
        "period": "2026-Q3",
        "context_digest": context["context_digest"],
        "watch_outcomes": [{"symbol": "AAA", "outcome": "KEEP_WATCH"}],
        "candidate_outcomes": candidate_outcomes(context, "WATCH_PROPOSAL"),
        "ready_outcomes": [],
    }
    body = "Reviewed quarterly fixture"
    manifest["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    validate_watch_letter_manifest(radar, "2026-Q3", manifest, body=body)
    with pytest.raises(ContractError, match="body does not match"):
        validate_watch_letter_manifest(radar, "2026-Q3", manifest, body=body + " replaced")

    manifest["candidate_outcomes"] = []
    with pytest.raises(ContractError, match="cover the current candidates"):
        validate_watch_letter_manifest(radar, "2026-Q3", manifest)

    with pytest.raises(ContractError, match="YYYY-QN"):
        watch_letter_context(radar, "2026-Q03")


def test_manifest_becomes_stale_when_bound_watch_context_changes(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    context = watch_letter_context(radar, "2026-Q3")
    manifest = {
        "period": "2026-Q3",
        "context_digest": context["context_digest"],
        "watch_outcomes": [{"symbol": "AAA", "outcome": "KEEP_WATCH"}],
        "candidate_outcomes": candidate_outcomes(context),
        "ready_outcomes": [],
    }
    case = radar.get_case_by_symbol("AAA")
    case_id = case["id"]
    assert isinstance(case_id, int)
    radar.add_watch_condition(case_id, "operating", "A newly confirmed condition")

    with pytest.raises(ContractError, match="context is stale"):
        validate_watch_letter_manifest(radar, "2026-Q3", manifest)


def test_old_candidate_decision_does_not_bind_to_new_episode(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    with radar.connect() as connection:
        connection.execute(
            "UPDATE candidate_inbox SET metrics_json=? WHERE symbol='BBB'",
            (json.dumps({"first_entry_month": "2026-09"}),),
        )

    context = watch_letter_context(radar, "2026-Q3")
    assert context["awaiting_candidates"] == []


def ready_case(radar: RadarDB) -> int:
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text())
    payload.update(symbol="AD", name="Synthetic euro listing", immediate_investable=True)
    payload.pop("watch_condition")
    payload["review"]["missing_to_ready"] = "No open condition; fixture only"
    for snapshot in payload["snapshots"].values():
        snapshot["price_date"] = "2026-10-02"
    payload["snapshots"]["case"].update(
        symbol="AD", currency="EUR", provider="yahoo_chart:AD.AS", price=31.5,
    )
    return radar.import_case(payload)


def test_ready_reference_and_confirmed_holding_boundary(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    case_id = ready_case(radar)
    radar.record_snapshot(case_id, MarketSnapshot(
        "AD", "case", 99, "2026-10-14", "2026-10-15T00:00:00Z",
        "USD", "nasdaq_info", "unverified fixture observation",
    ))
    first = watch_letter_context(radar, "2026-Q4")
    item = first["ready_cases"][0]
    assert item["id"] == case_id
    assert item["reference"]["price"] == 31.5
    assert item["reference"]["currency"] == "EUR"
    assert item["reference"]["price_date"] == "2026-10-02"
    assert item["position_link"] == "UNCONFIRMED"
    position = {
        "symbol": "AD", "name": "Fixture holding", "kind": "stock", "currency": "EUR",
        "average_price": 31.5, "quantity": 1, "invested_amount": 31.5,
        "objective": "Fixture", "horizon": "Fixture", "exit_strategy": "Fixture",
        "baseline_as_of": "2026-10-02", "provenance": "Synthetic test only",
    }
    radar.import_position(position, confirmed_by="owner")
    assert watch_letter_context(radar, "2026-Q4")["ready_cases"]
    with radar.connect() as connection:
        connection.execute("UPDATE positions SET case_id=? WHERE symbol='AD'", (case_id,))
    assert watch_letter_context(radar, "2026-Q4")["ready_cases"] == []
    assert radar.get_case(case_id)["status"] == "READY"
    assert radar.show_position("AD")["quantity"] == 1


def test_ready_manifest_and_report_binding(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    ready_case(radar)
    context = watch_letter_context(radar, "2026-Q4")
    manifest = {
        "period": "2026-Q4", "context_digest": context["context_digest"],
        "watch_outcomes": [{"symbol": "AAA", "outcome": "KEEP_WATCH"}],
        "candidate_outcomes": candidate_outcomes(context),
        "ready_outcomes": [],
    }
    with pytest.raises(ContractError, match="cover the current symbols"):
        validate_watch_letter_manifest(radar, "2026-Q4", manifest)
    manifest["ready_outcomes"] = [{"symbol": "AD", "outcome": "NO_DECISION"}]
    validate_watch_letter_manifest(radar, "2026-Q4", manifest)
    report = tmp_path / "BBB.md"
    report.write_text("Changed fixture conclusion")
    with pytest.raises(ContractError, match="context is stale"):
        validate_watch_letter_manifest(radar, "2026-Q4", manifest)
    report.unlink()
    with pytest.raises(ContractError, match="candidate report"):
        watch_letter_context(radar, "2026-Q4")


def test_candidate_ready_uses_single_admission_owner(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    candidate = radar.show_candidate("BBB")
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text())
    payload.update(symbol="BBB", name="BBB Corp", immediate_investable=True)
    payload["snapshots"]["case"]["symbol"] = "BBB"
    payload.pop("watch_condition")
    case_id = radar.promote_candidate(int(str(candidate["id"])), payload)
    assert radar.get_case(case_id)["status"] == "READY"
    assert radar.show_candidate("BBB")["status"] == "PROMOTED"
    assert radar.show_candidate("BBB")["case_id"] == case_id
    assert watch_letter_context(radar, "2026-Q4")["awaiting_candidates"] == []
    assert radar.get_open_conditions(case_id) == []


def test_candidate_completion_requires_report_and_retries_are_idempotent(tmp_path: Path) -> None:
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    with pytest.raises(ContractError, match="report"):
        radar.record_candidate_decision("BBB", "AWAITING_USER", "fixture missing report", decided_by="autonomous-research")
    args = dict(report_path=str(tmp_path / "BBB.md"), reader_text="Fixture complete", decided_by="autonomous-research")
    first = radar.record_candidate_decision("BBB", "AWAITING_USER", "fixture completed", **args)
    assert radar.record_candidate_decision("BBB", "AWAITING_USER", "fixture completed", **args) == first
    ended = radar.record_candidate_decision("BBB", "DEFER_EPISODE", "fixture episode ended", decided_by="autonomous-research", signal_date="2026-08")
    with radar.connect() as connection:
        connection.execute("""INSERT INTO candidate_inbox(stable_identity,symbol,name,kind,region,mic,status,
            first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json)
            SELECT stable_identity,symbol,name,kind,region,mic,'OPEN',first_seen_cycle_id,last_seen_cycle_id,lane,?
            FROM candidate_inbox WHERE symbol='BBB' ORDER BY id DESC LIMIT 1""", ('{"first_entry_month":"2026-09"}',))
    assert radar.record_candidate_decision("BBB", "DEFER_EPISODE", "fixture episode ended", decided_by="autonomous-research", signal_date="2026-08") == ended
    with pytest.raises(ContractError, match="ambiguous"):
        radar.show_candidate("BBB")
    selected = radar.next_research_candidate()
    assert selected is not None
    assert radar.show_candidate(candidate_id=int(str(selected["id"])))["status"] == "OPEN"


def test_same_symbol_candidates_bind_manifest_and_exact_cli_readback(tmp_path: Path, monkeypatch) -> None:
    from test_cli_smoke import run_cli
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    with radar.connect() as connection:
        second = connection.execute("""INSERT INTO candidate_inbox(
            stable_identity,symbol,name,kind,region,mic,status,
            first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json)
            SELECT 'DE:BBB',symbol,'Other listing',kind,'DE','XETR',status,
                   first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json
            FROM candidate_inbox WHERE symbol='BBB'""").lastrowid
    radar.record_candidate_decision("BBB", "AWAITING_USER", "Second listing research",
        candidate_id=second, signal_date="2026-08", report_path=str(tmp_path / "BBB.md"),
        reader_text="Second identity", decided_by="autonomous-research")
    context = watch_letter_context(radar, "2026-Q3")
    rows = context["awaiting_candidates"]
    assert len(rows) == 2 and len({r["candidate_id"] for r in rows}) == 2
    body = "Two separately reviewed synthetic listings"
    manifest: dict[str, object] = dict(period="2026-Q3", context_digest=context["context_digest"],
        body_sha256=hashlib.sha256(body.encode()).hexdigest(),
        watch_outcomes=[dict(symbol="AAA", outcome="KEEP_WATCH")], ready_outcomes=[],
        candidate_outcomes=candidate_outcomes(context))
    validate_watch_letter_manifest(radar, "2026-Q3", manifest, body=body)
    for row in rows:
        assert row["signal_date"] == "2026-08"
        result = run_cli("show-candidate", "--db", str(radar.path), "--candidate-id", str(row["candidate_id"]))
        assert result.returncode == 0, result.stderr
        shown = json.loads(result.stdout)
        assert shown["id"] == row["candidate_id"]
        assert shown["stable_identity"] == row["stable_identity"]
        assert shown["latest_decision"]["signal_date"] == row["signal_date"]
    # Actual quarterly consumer with synthetic transport; no external mail.
    import runpy
    import sys
    from opportunity_radar import mailer
    sends = []
    class FixtureMail:
        def find_verified(self, subject, recipient):
            return None
        def send_and_verify(self, subject, recipient, delivered_body):
            sends.append(delivered_body)
            return "synthetic-quarterly-message"
    monkeypatch.setattr(mailer, "HimalayaTransport", FixtureMail)
    monkeypatch.setenv("OPPORTUNITY_RADAR_DB", str(radar.path))
    monkeypatch.setenv("OPPORTUNITY_RADAR_RECIPIENT", "fixture@example.com")
    body_path = tmp_path / "brief.md"
    manifest_path = tmp_path / "manifest.json"
    body_path.write_text(body)
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(sys, "argv", ["quarterly", "--period", "2026-Q3",
        "--body", str(body_path), "--manifest", str(manifest_path)])
    consumer = runpy.run_path("scripts/run_quarterly_watch_mailer.py", run_name="quarterly_fixture")
    assert consumer["main"]() == 0
    assert consumer["main"]() == 0
    assert sends == [body]
    assert radar.get_mail_receipt("watch-quarterly:2026-Q3") is not None
    ambiguous = run_cli("show-candidate", "--db", str(radar.path), "--symbol", "BBB")
    assert ambiguous.returncode != 0 and "ambiguous" in ambiguous.stderr
    with pytest.raises(ContractError, match="ambiguous"):
        radar.record_candidate_decision("BBB", "DEFER_EPISODE", "must not select newest", decided_by="autonomous-research")
    for key, bad in (("candidate_id", None), ("candidate_id", second),
                     ("stable_identity", "WRONG"), ("signal_date", "2026-09")):
        changed = json.loads(json.dumps(manifest))
        if bad is None:
            del changed["candidate_outcomes"][0][key]
        else:
            changed["candidate_outcomes"][0][key] = bad
        with pytest.raises(ContractError, match="exact candidate_id"):
            validate_watch_letter_manifest(radar, "2026-Q3", changed, body=body)


def test_rejected_position_link_keeps_ready_visible_and_valid_link_is_held(tmp_path: Path) -> None:
    from test_positions import position_payload
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    case_id = ready_case(radar)
    payload = dict(position_payload(), symbol="OTHER", linked_case_symbol="AD")
    for operation in (radar.preview_position, lambda p: radar.import_position(p, confirmed_by="owner")):
        with pytest.raises(ContractError, match="instrument identity"):
            operation(payload)
    assert [r["id"] for r in watch_letter_context(radar, "2026-Q4")["ready_cases"]] == [case_id]
    payload["symbol"] = " ad "
    assert radar.preview_position(payload)["linked_case_id"] == case_id
    radar.import_position(payload, confirmed_by="owner")
    assert watch_letter_context(radar, "2026-Q4")["ready_cases"] == []
    assert radar.list_positions()[0]["case_id"] == case_id
    assert radar.monthly_position_review_status("2026-10")["active_symbols"] == ["AD"]
    assert radar.get_case(case_id)["status"] == "READY"
