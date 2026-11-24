"""Fail-closed contract tests for the bounded OI v1 provenance migration helper."""

import copy
import json
from datetime import date, timedelta

import pytest
from gspread.worksheet import ValueRange

from src.config.settings import OI_BASKET_ID, OI_SYMBOLS
from src.scripts import migrate_oi_v1_provenance as migration
from src.scripts.migrate_oi_v1_provenance import (
    VERIFIED_END_DATE,
    VERIFIED_START_DATE,
    plan_verified_oi_provenance_updates,
)


def _provenance(value):
    return {
        "value": value,
        "basket_id": OI_BASKET_ID,
        "provider": "coinalyze",
        "endpoint": "/v1/open-interest-history",
        "interval": "daily",
        "field": "c",
        "convert_to_usd": True,
        "expected_symbols": list(OI_SYMBOLS),
        "observed_symbols": list(OI_SYMBOLS),
        "expected_symbol_count": 9,
        "observed_symbol_count": 9,
        "coverage_pct": 100.0,
    }


def _rows():
    start = date.fromisoformat(VERIFIED_START_DATE)
    end = date.fromisoformat(VERIFIED_END_DATE)
    rows = []
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        rows.append({
            "date": day,
            "perp_oi_usd": float(100 + offset),
            "source_status_json": json.dumps({"oi": "ok", "coinbase": "ok"}),
        })
    rows.append({
        "date": "2026-07-12",
        "perp_oi_usd": 9999.0,
        "source_status_json": json.dumps({"oi": "ok", "coinbase": "ok"}),
    })
    assert len(rows) == 641
    return rows


def _refetched(rows):
    return {
        row["date"]: _provenance(row["perp_oi_usd"])
        for row in rows
        if VERIFIED_START_DATE <= row["date"] <= VERIFIED_END_DATE
    }


def test_migration_plans_only_verified_window_and_only_source_status_changes():
    rows = _rows()
    before = copy.deepcopy(rows)
    refetched = _refetched(rows)

    updates = plan_verified_oi_provenance_updates(rows, refetched)

    assert len(updates) == 640
    assert set(updates) == set(refetched)
    assert rows == before
    for date_value, new_status_json in updates.items():
        status = json.loads(new_status_json)
        assert status["coinbase"] == "ok"
        assert status["oi"] == "ok"
        assert status["oi_basket_v1"]["basket_id"] == OI_BASKET_ID
        assert "value" not in status["oi_basket_v1"]


@pytest.mark.parametrize(
    "refetched",
    [
        lambda rows: {VERIFIED_START_DATE: _provenance(100.0)},
        lambda rows: {
            **_refetched(rows),
            VERIFIED_START_DATE: _provenance(100.02),
        },
        lambda rows: {
            **_refetched(rows),
            VERIFIED_START_DATE: {**_provenance(100.0), "coverage_pct": 99.99},
        },
    ],
)
def test_migration_fails_closed_before_any_update_for_incomplete_or_mismatched_refetch(refetched):
    rows = _rows()
    with pytest.raises(ValueError):
        plan_verified_oi_provenance_updates(rows, refetched(rows))


def test_plan_cli_refetches_all_640_days_in_safe_chunks_and_never_writes(monkeypatch, capsys):
    rows = _rows()[:-1]
    sheet = object()
    calls = []

    monkeypatch.setattr(migration, "get_sheet", lambda name: sheet)
    monkeypatch.setattr(
        migration,
        "read_all_values",
        lambda actual_sheet, *, unformatted: [
            ["date", "perp_oi_usd", "source_status_json"],
            *[[row["date"], row["perp_oi_usd"], row["source_status_json"]] for row in rows],
        ],
    )

    def fetch(start, end):
        calls.append((start, end))
        return {
            row["date"]: _provenance(row["perp_oi_usd"])
            for row in rows if start <= row["date"] <= end
        }

    monkeypatch.setattr(migration, "fetch_open_interest_provenance", fetch)
    monkeypatch.setattr(migration.time, "sleep", lambda _: None)

    assert migration.main(["--plan"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert calls == [
        ("2024-10-10", "2025-03-18"),
        ("2025-03-19", "2025-08-25"),
        ("2025-08-26", "2026-02-01"),
        ("2026-02-02", "2026-07-11"),
    ]
    assert payload["mode"] == "plan_only_no_sheet_writes"
    assert payload["verified_day_count"] == 640
    assert payload["changed_column"] == "source_status_json"


class _FakeApplySheet:
    def __init__(self, values, *, readback_override=None, event_log=None, backup_dir=None):
        self.values = copy.deepcopy(values)
        self.readback_override = readback_override
        self.event_log = event_log if event_log is not None else []
        self.backup_dir = backup_dir
        self.batch_updates = []

    def batch_update(self, updates, **kwargs):
        if self.backup_dir is not None:
            assert list(self.backup_dir.glob("oi_v1_provenance_backup_*.json"))
            self.event_log.append("backup_present_before_batch_update")
        self.event_log.append("batch_update")
        self.batch_updates.append((copy.deepcopy(updates), kwargs))
        for update in updates:
            col = ord(update["range"][0]) - ord("A")
            row = int(update["range"][1:]) - 1
            self.values[row][col] = update["values"][0][0]

    def batch_get(self, ranges, **kwargs):
        self.event_log.append("batch_get")
        if self.readback_override is not None:
            return self.readback_override(ranges)
        return [
            ValueRange.from_json(
                {
                    "range": cell_range,
                    "majorDimension": "ROWS",
                    "values": [[self._value_at(cell_range)]],
                }
            )
            for cell_range in ranges
        ]

    def _value_at(self, cell_range):
        col = ord(cell_range[0]) - ord("A")
        row = int(cell_range[1:]) - 1
        return self.values[row][col]


def _apply_values(rows):
    return [
        ["date", "perp_oi_usd", "source_status_json", "untouched"],
        *[
            [row["date"], row["perp_oi_usd"], row["source_status_json"], "do-not-touch"]
            for row in rows
        ],
    ]


def _patch_cli_dependencies(monkeypatch, sheet, rows, refetched):
    monkeypatch.setattr(migration, "get_sheet", lambda name: sheet)
    monkeypatch.setattr(migration, "read_all_values", lambda actual_sheet, *, unformatted: sheet.values)
    monkeypatch.setattr(migration, "fetch_open_interest_provenance", lambda start, end: {
        day: provenance for day, provenance in refetched.items() if start <= day <= end
    })
    monkeypatch.setattr(migration.time, "sleep", lambda _: None)


def test_default_cli_never_calls_sheet_write_api(monkeypatch, capsys):
    rows = _rows()[:-1]
    sheet = _FakeApplySheet(_apply_values(rows))
    _patch_cli_dependencies(monkeypatch, sheet, rows, _refetched(rows))

    assert migration.main([]) == 0

    assert sheet.batch_updates == []
    assert json.loads(capsys.readouterr().out)["mode"] == "plan_only_no_sheet_writes"


def test_apply_writes_only_source_status_cells_for_exact_verified_scope(monkeypatch, tmp_path, capsys):
    rows = _rows()[:-1]
    sheet = _FakeApplySheet(_apply_values(rows))
    _patch_cli_dependencies(monkeypatch, sheet, rows, _refetched(rows))

    assert migration.main(["--apply", "--backup-dir", str(tmp_path)]) == 0

    assert len(sheet.batch_updates) == 1
    updates, kwargs = sheet.batch_updates[0]
    assert kwargs["value_input_option"] == "RAW"
    assert len(updates) == 640
    assert {item["range"][0] for item in updates} == {"C"}
    assert {int(item["range"][1:]) for item in updates} == set(range(2, 642))
    assert all(item["values"] and len(item["values"][0]) == 1 for item in updates)
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "apply"
    assert payload["verified_count"] == 640
    assert payload["backup_path"].startswith(str(tmp_path))


def test_apply_validation_failure_causes_zero_writes_and_no_backup(monkeypatch, tmp_path):
    rows = _rows()[:-1]
    sheet = _FakeApplySheet(_apply_values(rows))
    broken = _refetched(rows)
    broken[VERIFIED_START_DATE]["coverage_pct"] = 99.0
    _patch_cli_dependencies(monkeypatch, sheet, rows, broken)

    with pytest.raises(ValueError, match="exact complete OI v1 basket"):
        migration.main(["--apply", "--backup-dir", str(tmp_path)])

    assert sheet.batch_updates == []
    assert list(tmp_path.iterdir()) == []


def test_apply_persists_backup_before_its_single_batch_write(monkeypatch, tmp_path):
    rows = _rows()[:-1]
    events = []
    sheet = _FakeApplySheet(_apply_values(rows), event_log=events, backup_dir=tmp_path)
    _patch_cli_dependencies(monkeypatch, sheet, rows, _refetched(rows))

    assert migration.main(["--apply", "--backup-dir", str(tmp_path)]) == 0

    backups = list(tmp_path.glob("oi_v1_provenance_backup_*.json"))
    assert len(backups) == 1
    assert events.index("batch_update") > 0
    backup = json.loads(backups[0].read_text())
    assert backup["scope"]["day_count"] == 640
    assert len(backup["original_source_status_json"]) == 640


def test_apply_readback_mismatch_raises_with_backup_reference(monkeypatch, tmp_path):
    rows = _rows()[:-1]
    sheet = _FakeApplySheet(
        _apply_values(rows),
        readback_override=lambda ranges: [{"values": [["unexpected"]]} for _ in ranges],
    )
    _patch_cli_dependencies(monkeypatch, sheet, rows, _refetched(rows))

    with pytest.raises(RuntimeError, match=r"read-back mismatch.*oi_v1_provenance_backup_"):
        migration.main(["--apply", "--backup-dir", str(tmp_path)])

    assert len(sheet.batch_updates) == 1
    assert len(list(tmp_path.glob("oi_v1_provenance_backup_*.json"))) == 1
