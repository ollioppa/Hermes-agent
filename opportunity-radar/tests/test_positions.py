import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from opportunity_radar.db import RadarDB
from opportunity_radar.transitions import ContractError


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "opportunity_radar.cli", *args],
        text=True,
        capture_output=True,
        env=dict(os.environ, PYTHONPATH="src"),
    )


def position_payload() -> dict[str, object]:
    return {
        "symbol": "AAA",
        "name": "AAA Corp",
        "kind": "stock",
        "currency": "EUR",
        "linked_case_symbol": None,
        "purchase_date": None,
        "purchase_date_is_approximate": False,
        "average_price": 100.0,
        "quantity": 10.0,
        "invested_amount": 1000.0,
        "objective": "small asymmetric equity position",
        "horizon": "three years",
        "exit_strategy": "Exit if the investment thesis breaks",
        "benchmark_symbol": None,
        "baseline_as_of": "2026-09-23",
        "provenance": "Synthetic test position; no broker data",
    }


def write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "position.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_position_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    radar = RadarDB(db)
    radar.initialize()
    payload_path = write_payload(tmp_path, position_payload())

    result = run_cli(
        "import-position", "--db", str(db), "--input", str(payload_path), "--dry-run"
    )

    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert preview["status"] == "ACTIVE"
    assert preview["baseline_version"] == 1
    assert preview["purchase_date"] is None
    with radar.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM position_baselines").fetchone()[0] == 0


@pytest.mark.parametrize("symbol,kind", [("OTHER", "stock"), ("AAA", "etf")])
def test_position_link_requires_matching_instrument_in_preview_and_import(tmp_path, symbol, kind):
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    radar.add_case("AAA", "Synthetic case", "stock", "SPY")
    payload = dict(position_payload(), symbol=symbol, kind=kind, linked_case_symbol="AAA")
    for operation in (radar.preview_position, lambda p: radar.import_position(p, confirmed_by="owner")):
        with pytest.raises(ContractError, match="instrument identity"):
            operation(payload)
    with radar.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM position_baselines").fetchone()[0] == 0


def test_position_accepts_only_existing_bound_alias(tmp_path: Path) -> None:
    from test_quarterly_watch import seeded_radar
    radar = seeded_radar(tmp_path / "radar.sqlite3")
    case = radar.get_case_by_symbol("AAA")
    payload = dict(position_payload(), symbol="BBB", linked_case_symbol="AAA")
    with pytest.raises(ContractError, match="instrument identity"):
        radar.preview_position(payload)
    with radar.connect() as connection:
        connection.execute("INSERT INTO case_identity_aliases(stable_identity,case_id) VALUES (?,?)",
                           ("US:BBB", case["id"]))
    assert radar.preview_position(payload)["linked_case_id"] == case["id"]
    radar.import_position(payload, confirmed_by="owner")
    assert radar.show_position("BBB")["case_id"] == case["id"]


def test_confirmed_import_creates_one_position_without_changing_radar(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    radar = RadarDB(db)
    radar.initialize()
    radar.add_case("ZZZ", "Unrelated Radar Case", "stock", "SPY")
    cases_before = radar.list_cases()
    payload_path = write_payload(tmp_path, position_payload())

    imported = run_cli(
        "import-position", "--db", str(db), "--input", str(payload_path),
        "--confirmed-by", "owner",
    )
    listed = run_cli("list-positions", "--db", str(db))
    shown = run_cli("show-position", "--db", str(db), "--symbol", "AAA")

    assert imported.returncode == 0, imported.stderr
    assert listed.returncode == 0, listed.stderr
    assert shown.returncode == 0, shown.stderr
    listing = json.loads(listed.stdout)
    assert len(listing) == 1
    assert listing[0]["purchase_date"] is None
    assert listing[0]["objective"] == "small asymmetric equity position"
    position = json.loads(shown.stdout)
    assert position["status"] == "ACTIVE"
    assert position["quantity"] == 10.0
    assert position["purchase_date"] is None
    assert position["purchase_date_is_approximate"] is False
    assert position["baselines"][0]["version"] == 1
    assert position["baselines"][0]["confirmed_by"] == "owner"
    assert radar.list_cases() == cases_before


def test_known_approximate_purchase_date_is_visible(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    radar = RadarDB(db)
    radar.initialize()
    payload = position_payload()
    payload["purchase_date"] = "2026-01-15"
    payload["purchase_date_is_approximate"] = True
    radar.import_position(payload, confirmed_by="owner")

    result = radar.show_position("AAA")

    assert result["purchase_date"] == "2026-01-15"
    assert result["purchase_date_is_approximate"] is True


def test_approximate_flag_without_date_is_rejected(tmp_path: Path) -> None:
    payload = position_payload()
    payload["purchase_date_is_approximate"] = True

    with pytest.raises(ContractError, match="still requires purchase_date"):
        RadarDB(tmp_path / "radar.sqlite3").preview_position(payload)


def test_position_requires_owner_and_rejects_duplicate_active_symbol(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    radar = RadarDB(db)
    radar.initialize()
    payload = position_payload()

    with pytest.raises(ContractError, match="confirmed-by owner"):
        radar.import_position(payload, confirmed_by="autonomous-research")

    radar.import_position(payload, confirmed_by="owner")
    with pytest.raises(ContractError, match="ACTIVE position"):
        radar.import_position(payload, confirmed_by="owner")


def test_confirmed_baseline_cannot_be_updated_or_deleted(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    radar = RadarDB(db)
    radar.initialize()
    radar.import_position(position_payload(), confirmed_by="owner")

    with radar.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE position_baselines SET change_reason='rewritten' WHERE version=1"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM position_baselines WHERE version=1")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("average_price", "Infinity"),
        ("name", None),
        ("objective", None),
        ("horizon", ""),
        ("exit_strategy", None),
        ("provenance", None),
    ],
)
def test_position_rejects_invalid_required_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    payload = position_payload()
    payload[field] = value

    with pytest.raises(ContractError):
        RadarDB(tmp_path / "radar.sqlite3").import_position(payload, confirmed_by="owner")


def test_dry_run_with_link_does_not_create_missing_database(tmp_path: Path) -> None:
    db = tmp_path / "missing.sqlite3"
    payload = position_payload()
    payload["linked_case_symbol"] = "AAA"
    radar = RadarDB(db)

    with pytest.raises(ContractError, match="not available"):
        radar.preview_position(payload)
    assert not db.exists()


def test_confirmed_import_reads_back_normalized_symbol(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    RadarDB(db).initialize()
    payload = position_payload()
    payload["symbol"] = " AAA "
    payload_path = write_payload(tmp_path, payload)

    imported = run_cli(
        "import-position", "--db", str(db), "--input", str(payload_path),
        "--confirmed-by", "owner",
    )

    assert imported.returncode == 0, imported.stderr
    assert json.loads(imported.stdout)["symbol"] == "AAA"


def test_failed_baseline_insert_rolls_back_position(tmp_path: Path) -> None:
    db = tmp_path / "radar.sqlite3"
    radar = RadarDB(db)
    radar.initialize()
    with radar.connect() as connection:
        connection.execute(
            """CREATE TRIGGER reject_proof_baseline BEFORE INSERT ON position_baselines
               BEGIN SELECT RAISE(ABORT, 'proof baseline failure'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="proof baseline failure"):
        radar.import_position(position_payload(), confirmed_by="owner")

    with radar.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
