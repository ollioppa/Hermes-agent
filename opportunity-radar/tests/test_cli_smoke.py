import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from opportunity_radar.db import RadarDB, candidate_suppression_reason, same_candidate_episode


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "opportunity_radar.cli", *args],
        text=True,
        capture_output=True,
        env=dict(os.environ, PYTHONPATH="src"),
    )


def test_research_work_price_revisit_and_capacity_use_existing_owner(tmp_path: Path) -> None:
    from datetime import date
    from opportunity_radar.db import active_research_count
    db = tmp_path / "research.sqlite3"
    seed_candidate(db)
    radar = RadarDB(db)
    selected = radar.next_research_candidate()
    assert selected is not None
    report = tmp_path / "research.md"
    report.write_text("# Explicit research fixture\nQuellenstand 2026-09-23\nPreisablehnung, kein Liveurteil.")
    radar.save_candidate_work(int(str(selected["id"])), signal_date="2026-08", report_path=str(report),
                              source_as_of="2026-09-23", resume_from="Complete valuation")
    resumed = radar.next_research_candidate()
    assert resumed is not None and isinstance(resumed["report_handoff"], list)
    assert resumed["report_handoff"][0]["report_text"].startswith("# Explicit")
    radar.record_candidate_decision("AAA", "DEFER_EPISODE", "Price only", report_path=str(report),
        reader_text="Explicit fixture", revisit_after=date.today().isoformat(), decided_by="autonomous-research")
    revisited = radar.next_research_candidate()
    assert revisited is not None and revisited["status"] == "OPEN" and radar.list_cases() == []
    radar.record_candidate_decision("AAA", "AWAITING_USER", "Completed fixture", report_path=str(report),
        reader_text="Ready for human judgment", decided_by="autonomous-research")
    with radar.connect() as connection:
        assert active_research_count(connection) == 0
    assert radar.next_research_candidate() is None


def seed_candidate(db: Path, *, symbol: str = "AAA", signal_date: str = "2026-08") -> None:
    radar = RadarDB(db)
    radar.initialize()
    with radar.connect() as connection:
        cycle_cursor = connection.execute(
            """INSERT INTO screen_cycles(
                   cycle_key,cohort_index,provider,status,as_of,completed_at)
               VALUES (?,?,?,'COMPLETED',?,CURRENT_TIMESTAMP)""",
            (f"seed:{symbol}:{signal_date}", 0, "test", "2026-09-23"),
        )
        if cycle_cursor.lastrowid is None:
            raise RuntimeError("screen cycle insert returned no id")
        cycle_id = int(cycle_cursor.lastrowid)
        connection.execute(
            """INSERT INTO candidate_inbox(
                   stable_identity,symbol,name,kind,region,mic,status,
                   first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json)
               VALUES (?,?,?,?,?,?,'OPEN',?,?,?,?)""",
            (
                f"US:{symbol}", symbol, f"{symbol} Corp", "stock", "US", "XNYS",
                cycle_id, cycle_id, "TREND_NORMALIZATION",
                json.dumps({"first_entry_month": signal_date}),
            ),
        )


def test_cli_imports_lists_renders_and_invalidates_case(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    output = tmp_path / "radar.md"
    fixture = Path("tests/fixtures/stock_case.json").resolve()

    initialized = run_cli("init", "--db", str(db))
    imported = run_cli("import-case", "--db", str(db), "--input", str(fixture))
    listed = run_cli("list", "--db", str(db))
    rendered = run_cli("render", "--db", str(db), "--output", str(output))

    assert initialized.returncode == 0, initialized.stderr
    assert imported.returncode == 0, imported.stderr
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout)[0]["symbol"] == "UNH"
    assert rendered.returncode == 0, rendered.stderr
    assert "**UNH — WATCH**" in output.read_text(encoding="utf-8")
    assert "Kundenökonomie:" in output.read_text(encoding="utf-8")
    with sqlite3.connect(db) as connection:
        stored = json.loads(connection.execute("SELECT payload_json FROM reviews").fetchone()[0])
    assert stored["customer_economics"]["margin_source_and_use"] == "Explicit generated schema fixture; no investment research"

    invalidated = run_cli(
        "invalidate", "--db", str(db), "--symbol", "UNH", "--reason", "falsifier triggered"
    )
    rerendered = run_cli("render", "--db", str(db), "--output", str(output))

    assert invalidated.returncode == 0, invalidated.stderr
    assert rerendered.returncode == 0, rerendered.stderr
    assert "**UNH — WATCH**" not in output.read_text(encoding="utf-8")
    assert "**UNH — INVALIDATED**" in output.read_text(encoding="utf-8")
    assert "Grund: falsifier triggered" in output.read_text(encoding="utf-8")


def test_cli_imports_immediately_investable_case_directly_to_ready(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    output = tmp_path / "radar.md"
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text(encoding="utf-8"))
    payload["immediate_investable"] = True
    payload["review"]["missing_to_ready"] = "Keine offene Bedingung; Review ist entscheidungsreif."
    payload.pop("watch_condition")
    direct_ready = tmp_path / "direct-ready.json"
    direct_ready.write_text(json.dumps(payload), encoding="utf-8")

    imported = run_cli("import-case", "--db", str(db), "--input", str(direct_ready))
    listed = run_cli("list", "--db", str(db))
    evaluated = run_cli("evaluate", "--db", str(db), "--symbol", "UNH")
    rendered = run_cli("render", "--db", str(db), "--output", str(output))

    assert imported.returncode == 0, imported.stderr
    assert json.loads(listed.stdout)[0]["status"] == "READY"
    assert evaluated.returncode == 0, evaluated.stderr
    assert json.loads(evaluated.stdout)["case_return_pct"] == 0.0
    assert rendered.returncode == 0, rendered.stderr
    assert "**UNH — READY**" in output.read_text(encoding="utf-8")
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM watch_conditions").fetchone()[0] == 0
        assert connection.execute("SELECT immediate_investable FROM shadow_entries").fetchone()[0] == 1
        assert connection.execute(
            "SELECT from_status || '->' || to_status FROM transitions"
        ).fetchone()[0] == "INBOX->READY"
        assert connection.execute(
            "SELECT COUNT(*) FROM market_snapshots WHERE role = 'ready'"
        ).fetchone()[0] == 1

    from opportunity_radar.quarterly_watch import watch_letter_context
    prior = watch_letter_context(RadarDB(db), "2026-Q4")["ready_cases"][0]
    demoted = run_cli("deprioritize", "--db", str(db), "--symbol", "UNH",
                      "--reason", "vorerst weniger wichtig", "--confirmed-by", "owner")
    assert demoted.returncode == 0, demoted.stderr
    assert run_cli("render", "--db", str(db), "--output", str(output)).returncode == 0
    assert "**UNH — WATCH**" in output.read_text()
    assert "Priorität zurückgestellt (Owner): vorerst weniger wichtig" in output.read_text()
    current = watch_letter_context(RadarDB(db), "2026-Q4")["watch_cases"][0]
    assert current["review"] == prior["review"] and current["reference"] == prior["reference"]
    assert current["open_conditions"] == [] and current["transition_reason"].startswith("Priorität")
    assert run_cli("deprioritize", "--db", str(db), "--symbol", "UNH",
                   "--reason", "again", "--confirmed-by", "owner").returncode != 0
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM watch_conditions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM market_snapshots WHERE role='ready'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1


def test_failed_import_leaves_no_partial_case(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text(encoding="utf-8"))
    payload.pop("review")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")

    result = run_cli("import-case", "--db", str(db), "--input", str(broken))
    listed = run_cli("list", "--db", str(db))

    assert result.returncode != 0
    assert json.loads(listed.stdout) == []


def test_candidate_research_incomplete_is_stored_read_back_and_deferred(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    seed_candidate(db)

    invalid_date = run_cli(
        "candidate-decision", "--db", str(db), "--symbol", "AAA",
        "--decision", "RESEARCH_INCOMPLETE", "--reason", "annual filing pending",
        "--revisit-after", "29990101", "--decided-by", "autonomous-research",
    )
    assert invalid_date.returncode != 0

    recorded = run_cli(
        "candidate-decision", "--db", str(db), "--symbol", "AAA",
        "--decision", "RESEARCH_INCOMPLETE", "--reason", "annual filing pending",
        "--revisit-after", "2999-01-01", "--report-path", "output/reviews/automated/AAA.md",
        "--reader-text", "One filing is missing.", "--revisit-trigger", "   ",
        "--decided-by", "autonomous-research",
    )
    shown = run_cli("show-candidate", "--db", str(db), "--symbol", "AAA")
    next_candidate = run_cli("next-candidate", "--db", str(db))

    assert recorded.returncode == 0, recorded.stderr
    assert shown.returncode == 0, shown.stderr
    payload = json.loads(shown.stdout)
    assert payload["status"] == "OPEN"
    assert payload["latest_decision"]["decision"] == "RESEARCH_INCOMPLETE"
    assert payload["latest_decision"]["revisit_after"] == "2999-01-01"
    assert payload["latest_decision"]["revisit_trigger"] is None
    assert payload["latest_decision"]["report_path"] == "output/reviews/automated/AAA.md"
    assert next_candidate.stdout.strip() == "NONE"

    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE candidate_decisions SET revisit_after='2000-01-01' WHERE symbol='AAA'"
        )
    due = run_cli("next-candidate", "--db", str(db))
    assert json.loads(due.stdout)["symbol"] == "AAA"


def test_screen_distorted_archives_and_suppresses_same_episode(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    seed_candidate(db)
    radar = RadarDB(db)
    radar.record_candidate_decision(
        "AAA", "SCREEN_DISTORTED", "2-for-1 split breaks the episode",
        decided_by="autonomous-research",
    )

    with radar.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_inbox WHERE stable_identity='US:AAA' AND status='OPEN'"
        ).fetchone()[0] == 0
        decision = connection.execute(
            """SELECT decision,reason,signal_date FROM candidate_decisions
               WHERE stable_identity='US:AAA' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    assert candidate_suppression_reason(decision, "2026-08") == (
        "current signal episode distorted: 2-for-1 split breaks the episode"
    )
    assert candidate_suppression_reason(decision, "2026-09") is None


def test_open_candidate_episode_is_not_rebound_by_a_later_signal() -> None:
    metrics = json.dumps({"first_entry_month": "2026-08", "latest_close": 100.0})
    assert same_candidate_episode(metrics, "2026-08") is True
    assert same_candidate_episode(metrics, "2026-09") is False


def test_autonomous_research_cannot_exclude_an_identity(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    seed_candidate(db)

    rejected = run_cli(
        "candidate-decision", "--db", str(db), "--symbol", "AAA",
        "--decision", "EXCLUDE", "--reason", "proof-only exclusion attempt",
        "--decided-by", "autonomous-research",
    )

    assert rejected.returncode != 0
    radar = RadarDB(db)
    shown = radar.show_candidate("AAA")
    assert shown["status"] == "OPEN"
    assert shown["latest_decision"] is None


def test_initialize_migrates_existing_candidate_decisions_without_data_loss(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            """CREATE TABLE candidate_decisions (
                   id INTEGER PRIMARY KEY,
                   stable_identity TEXT NOT NULL,
                   symbol TEXT NOT NULL,
                   decision TEXT NOT NULL CHECK(decision IN ('EXCLUDE','DEFER_EPISODE','AWAITING_USER')),
                   reason TEXT NOT NULL,
                   signal_date TEXT NOT NULL,
                   report_path TEXT,
                   reader_text TEXT,
                   decided_by TEXT NOT NULL,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   notified_at TEXT
               );
               INSERT INTO candidate_decisions(
                   stable_identity,symbol,decision,reason,signal_date,decided_by)
               VALUES ('US:AAA','AAA','AWAITING_USER','ready','2026-08','legacy');"""
        )

    radar = RadarDB(db)
    radar.initialize()

    with radar.connect() as connection:
        row = connection.execute(
            "SELECT decision,reason,revisit_after,revisit_trigger FROM candidate_decisions"
        ).fetchone()
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='candidate_decisions'"
        ).fetchone()[0]
    assert dict(row) == {
        "decision": "AWAITING_USER", "reason": "ready",
        "revisit_after": None, "revisit_trigger": None,
    }
    assert "RESEARCH_INCOMPLETE" in sql
    assert "SCREEN_DISTORTED" in sql


def test_archive_schema_migration_preserves_ids_links_and_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db) as c:
        c.executescript("""CREATE TABLE cases (
            id INTEGER PRIMARY KEY, symbol TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('stock','etf')), sector_symbol TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'INBOX', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE case_identity_aliases (stable_identity TEXT PRIMARY KEY,
            case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE legacy_link (id INTEGER PRIMARY KEY, case_id INTEGER REFERENCES cases(id));
            INSERT INTO cases VALUES (42,'AAA','AAA Corp','stock','XLV','ARCHIVED','2026-09-01');
            INSERT INTO case_identity_aliases VALUES ('US:AAA',42,'2026-09-01');
            INSERT INTO legacy_link VALUES (1,42);""")
    import pytest
    from opportunity_radar.transitions import ContractError
    broken = tmp_path / 'broken-legacy.sqlite3'
    with sqlite3.connect(db) as source, sqlite3.connect(broken) as destination:
        source.backup(destination)
        destination.execute('UPDATE legacy_link SET case_id=999')
    with pytest.raises(ContractError, match='foreign keys'):
        RadarDB(broken).initialize()
    with sqlite3.connect(broken) as c:
        assert 'symbol TEXT NOT NULL UNIQUE' in c.execute("SELECT sql FROM sqlite_master WHERE name='cases'").fetchone()[0]
        assert c.execute('SELECT id FROM cases').fetchone()[0] == 42
    radar = RadarDB(db); radar.initialize(); radar.initialize()
    with radar.connect() as c:
        assert c.execute("SELECT case_id FROM legacy_link").fetchone()[0] == 42
        assert c.execute("SELECT created_at FROM case_identity_aliases WHERE case_id=42").fetchone()[0] == "2026-09-01"
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    new_id = radar.add_case("AAA", "AAA Corp", "stock", "XLV")
    with radar.connect() as c:
        c.execute("INSERT INTO case_identity_aliases(stable_identity,case_id) VALUES ('US:AAA',?)", (new_id,))
        assert c.execute("SELECT COUNT(*) FROM case_identity_aliases WHERE stable_identity='US:AAA'").fetchone()[0] == 2
    with pytest.raises(sqlite3.IntegrityError):
        radar.add_case("AAA", "Duplicate active", "stock", "XLV")


def test_archive_reentry_screen_admission_and_historical_evaluation(tmp_path: Path) -> None:
    import runpy
    publish = runpy.run_path("scripts/run_trend_screening.py", run_name="screen_fixture")["publish"]
    db = tmp_path / "radar.sqlite3"; seed_candidate(db)
    radar = RadarDB(db)
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text())
    payload.update(symbol="AAA", name="AAA Corp", immediate_investable=True)
    payload.pop("watch_condition"); payload["snapshots"]["case"]["symbol"] = "AAA"
    old_candidate = int(str(radar.show_candidate("AAA")["id"]))
    old_id = radar.promote_candidate(old_candidate, payload)
    old_shadow = radar.get_shadow_entry(old_id)
    position: dict[str, object] = dict(symbol='AAA',name='Synthetic holding',kind='stock',currency='USD',
        linked_case_symbol='AAA',average_price=100,quantity=1,invested_amount=100,
        objective='Fixture',horizon='Fixture',exit_strategy='Fixture',
        baseline_as_of='2026-09-08',provenance='Synthetic fixture only')
    radar.import_position(position,confirmed_by='owner')
    radar.transition(old_id, "ARCHIVED", "Synthetic ended opportunity")
    with radar.connect() as c:
        c.execute("UPDATE transitions SET created_at='2026-09-15 12:00:00' WHERE case_id=? AND to_status='ARCHIVED'", (old_id,))
    signal = dict(stable_identity="US:AAA",symbol="AAA",name="AAA Corp",kind="stock",region="US",mic="XNYS",
                  first_entry_month="2026-08",run_month="2026-01",latest_date="2026-10-01",current_ratio=1.01)
    from datetime import date
    assert publish(radar,[signal],as_of=date(2026,10,1),source_revision="old")['selected'] == 0
    signal['first_entry_month'] = '2026-09'
    assert publish(radar,[signal],as_of=date(2026,10,2),source_revision="new")['selected'] == 1
    selected = radar.next_research_candidate()
    assert selected is not None
    new_candidate = int(str(selected["id"]))
    for value in payload['snapshots'].values(): value['price_date'] = '2026-10-01'
    new_id = radar.promote_candidate(new_candidate,payload)
    assert new_id != old_id
    assert radar.get_case(old_id)['status'] == 'ARCHIVED'
    assert radar.get_case_by_symbol('AAA')['id'] == new_id
    assert radar.get_shadow_entry(old_id) == old_shadow
    new_shadow = radar.get_shadow_entry(new_id)
    assert new_shadow is not None and new_shadow['price_date'] == '2026-10-01'
    assert radar.show_candidate(candidate_id=new_candidate)['status'] == 'PROMOTED'
    assert radar.show_position('AAA')['case_id'] == old_id
    assert radar.preview_position(position)['linked_case_id'] == new_id
    for case_id in (old_id,new_id):
        result = run_cli('evaluate','--db',str(db),'--case-id',str(case_id))
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['case_id'] == case_id
    assert publish(radar,[dict(signal,first_entry_month='2026-10')],as_of=date(2026,11,1),source_revision="active")['selected'] == 0


def test_candidate_decision_requires_explicit_actor_before_database_write(tmp_path: Path) -> None:
    db = tmp_path / "missing.sqlite3"
    result = run_cli("candidate-decision", "--db", str(db), "--symbol", "AAA",
                     "--decision", "DEFER_EPISODE", "--reason", "Synthetic reason")
    assert result.returncode != 0 and "--decided-by" in result.stderr
    assert not db.exists()
    seed_candidate(db)
    result = run_cli("candidate-decision", "--db", str(db), "--symbol", "AAA",
                     "--decision", "DEFER_EPISODE", "--reason", "Synthetic reason",
                     "--decided-by", "autonomous-research")
    assert result.returncode == 0, result.stderr
    shown = RadarDB(db).show_candidate("AAA")
    assert shown["latest_decision"]["decided_by"] == "autonomous-research"


def test_stale_open_candidate_cannot_bypass_archived_episode(tmp_path: Path) -> None:
    import pytest
    from opportunity_radar.transitions import ContractError
    db=tmp_path/'radar.sqlite3'; seed_candidate(db)
    radar=RadarDB(db)
    payload=json.loads(Path('tests/fixtures/stock_case.json').read_text())
    payload.update(symbol='AAA',name='AAA Corp',immediate_investable=True)
    payload.pop('watch_condition');payload['snapshots']['case']['symbol']='AAA'
    old_id=radar.import_case(payload)
    radar.transition(old_id,'ARCHIVED','Synthetic direct opportunity ended')
    with radar.connect() as c:
        c.execute("UPDATE transitions SET created_at='2026-09-15' WHERE case_id=? AND to_status='ARCHIVED'",(old_id,))
    with pytest.raises(ContractError,match='archiv|episode'):
        radar.promote_candidate(int(str(radar.show_candidate('AAA')['id'])),payload)
    assert len(radar.list_cases())==1
    assert radar.show_candidate('AAA')['status']=='OPEN'
    radar.record_candidate_decision('AAA','EXCLUDE','Synthetic permanent human exclusion',decided_by='owner')
    import runpy
    from datetime import date
    publish=runpy.run_path('scripts/run_trend_screening.py',run_name='excluded_fixture')['publish']
    signal=dict(stable_identity='US:AAA',symbol='AAA',name='AAA Corp',kind='stock',region='US',mic='XNYS',
        first_entry_month='2026-09',run_month='2026-01',latest_date='2026-10-01',current_ratio=1.01)
    assert publish(radar,[signal],as_of=date(2026,10,2),source_revision='excluded')['selected']==0
