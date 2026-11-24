import json
import pytest
from datetime import date
from unittest.mock import MagicMock, call, patch

from src.config.settings import MACRO_DATA_COLUMNS, MACRO_DATA_COLUMN_TYPES
from src.services import backfill


@pytest.mark.parametrize("failure", ["write", "read", None])
def test_daily_real_window_failure_chain(monkeypatch, tmp_path, capsys, failure):
    import subprocess
    from src.scripts import run_daily as cli
    from src.services import windowed_sheets as windows
    monkeypatch.setattr(cli.sys, "argv", ["run_daily", "--write"])
    monkeypatch.setattr(cli, "LOCK_FILE", tmp_path / "daily.lock")
    monkeypatch.setattr(backfill, "MACRO_DATA_DAILY_ENABLED", False)
    monkeypatch.setattr(backfill, "_latest_completed_daily_date", lambda: "2026-07-21")
    rows = [["date", "btc"], ["2026-07-21", 100.0]]
    monkeypatch.setattr(backfill, "_build_db_rows", lambda *a, **k: rows)
    monkeypatch.setattr(backfill, "_build_market_data_rows", lambda *a, **k: rows)
    db, market = MagicMock(), MagicMock()
    db.get_all_values.return_value = rows
    if failure == "read":
        db.get_all_values.side_effect = OSError("history unavailable")
    market.get_all_values.side_effect = [[backfill.MARKET_DATA_HEADER], rows]
    monkeypatch.setattr(backfill, "get_sheet", lambda name: db if name == "DB" else market)
    upserts = MagicMock()
    monkeypatch.setattr(backfill, "upsert_rows", upserts)
    monkeypatch.setattr(windows, "WINDOWED_SHEETS_ENABLED", True)
    monkeypatch.setattr(windows, "WINDOWED_SHEET_CONFIG", {"30d": {"days": 30, "spreadsheet_id": "offline"}})
    monkeypatch.setattr(windows, "get_sheet_by_id", lambda _, name: name)
    writes = []
    def write(sheet, rows, **kwargs):
        writes.append(sheet)
        if failure == "write" and sheet == "DB":
            raise RuntimeError("write rejected")
    monkeypatch.setattr(windows, "batch_write", write)
    errors = {"stress_timeout": subprocess.TimeoutExpired("offline", 240),
              "stress_exit": subprocess.CalledProcessError(1, "offline"),
              "stress_os": OSError("child missing")}
    stress = MagicMock(side_effect=errors.get(failure))
    monkeypatch.setattr(subprocess, "run", stress)
    assert cli.main() == (2 if failure else 0)
    assert upserts.call_count == 2
    assert upserts.call_args_list[0].args == (db, rows[1:])
    assert upserts.call_args_list[1].args == (market, rows[1:])
    assert "MARKET_DATA" in writes
    stress.assert_not_called()
    stderr = capsys.readouterr().err
    if failure in ("write", "read"):
        assert f"DB:{failure}_failed" in stderr


def test_daily_lock_parallel_crash_release_and_stale_pid(tmp_path, monkeypatch):
    import os
    import select
    import subprocess
    import sys
    from src.scripts import run_daily as cli
    path = tmp_path / "daily.lock"
    path.write_text("stale-pid")
    with cli.FileLock(path):
        inode = path.stat().st_ino
    code = "from pathlib import Path; from src.scripts.run_daily import FileLock; import sys,time; " \
           "lock=FileLock(Path(sys.argv[1])); lock.__enter__(); print('held',flush=True); time.sleep(60)"
    holder = subprocess.Popen([sys.executable, "-B", "-c", code, str(path)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None
        assert select.select([holder.stdout], [], [], 10)[0], "holder failed to become ready"
        assert holder.stdout.readline().strip() == "held"
        held_pid = path.read_text()
        monkeypatch.setattr(cli, "LOCK_FILE", path)
        monkeypatch.setattr(cli.sys, "argv", ["run_daily", "--write"])
        daily = MagicMock()
        monkeypatch.setattr(cli, "run_daily", daily)
        assert cli.main() == 75
        daily.assert_not_called()
        assert path.read_text() == held_pid  # contender must not truncate
        holder.kill()
        holder.wait(timeout=10)
        with cli.FileLock(path):
            assert path.read_text() == str(os.getpid())
        assert path.stat().st_ino == inode
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)
        holder.stdout.close()


def test_daily_lock_does_not_mask_body_file_exists_error(tmp_path, monkeypatch):
    from src.scripts import run_daily as cli
    monkeypatch.setattr(cli.sys, "argv", ["run_daily", "--write"])
    monkeypatch.setattr(cli, "LOCK_FILE", tmp_path / "daily.lock")
    monkeypatch.setattr(cli, "run_daily", MagicMock(side_effect=FileExistsError("body error")))
    with pytest.raises(FileExistsError, match="body error"):
        cli.main()


def monthly_rows(count=65):
    rows = []
    for index in range(count):
        day = date(2020 + index // 12, index % 12 + 1, 1)
        rows.append((day, 100.0 + index))
    return rows


def valid_macro_rows() -> list[list[object]]:
    return backfill.build_macro_rows(
        finra={},
        nfci={date(2026, 7, 21): {"nfci_leverage": 0.1}},
        liquidity={},
        hy_oas={},
        bdc={},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )


def test_macro_builder_fetches_production_sources_and_returns_exact_wide_rows():
    base = monthly_rows()
    fred = {
        "CPIAUCSL": [(day, 100.0) for day, _ in base],
        "NFCILEVERAGE": base,
        "WALCL": base,
        "WTREGEN": base,
        "RRPONTSYD": base,
        "BAMLH0A0HYM2": [(base[-1][0], 3.4)],
    }
    bdc = [
        {
            "export_date": "2026-05-23",
            "bdc_as_of_date": "2026-05-16",
            "stage1_credit_quality": 101.0,
            "stage2_wrapper_repricing": 100.0,
            "stage3_funding_stress": 53.0,
            "stage4_credit_supply": 24.0,
            "stage5_macro_effects": 12.0,
            "stage6_feedback": 3.0,
            "regime_a_probability": 0.07,
            "regime_b_probability": 0.61,
            "regime_c_probability": 0.32,
            "status_code": "Orange",
            "source_status": "ok",
        }
    ]

    with (
        patch.object(backfill, "fetch_finra_margin", return_value=base),
        patch.object(backfill, "fetch_fred_series", side_effect=lambda sid, start, end: fred[sid]),
        patch.object(backfill, "load_verified_archive", return_value=[(base[0][0], 5.0)]),
        patch.object(
            backfill,
            "merge_archive_with_fred",
            return_value=[(day, 5.0, "archive") for day, _ in base[:-1]]
            + [(base[-1][0], 3.4, "current_fred")],
        ),
        patch.object(backfill, "load_bdc_exports", return_value=bdc),
        patch.object(
            backfill,
            "_fetch_yfinance_close",
            return_value={day.isoformat(): 100.0 + index for index, (day, _) in enumerate(base)},
        ),
    ):
        rows = backfill._build_macro_data_rows(
            "2026-07-22T10:00:00+00:00",
            start_override="2020-01-01",
        )

    assert rows[0] == MACRO_DATA_COLUMNS
    assert len(rows) > 2
    assert all(len(row) == len(MACRO_DATA_COLUMNS) for row in rows)
    assert rows[1][0] >= rows[-1][0]


def test_daily_nfci_fetch_keeps_full_expanding_percentile_history():
    source_rows = [(date(2026, 7, 1), 1.0)]
    fred_fetch = MagicMock(return_value=source_rows)
    with (
        patch.object(backfill, "fetch_finra_margin", return_value=source_rows),
        patch.object(backfill, "fetch_fred_series", fred_fetch),
        patch.object(backfill, "load_verified_archive", return_value=[(date(2020, 1, 1), 5.0)]),
        patch.object(backfill, "merge_archive_with_fred", return_value=[(date(2026, 7, 1), 3.0, "current_fred")]),
        patch.object(backfill, "_fetch_yfinance_close", return_value={"2026-07-01": 6000.0}),
        patch.object(backfill, "load_bdc_exports", return_value=[{"export_date": "2026-07-01"}]),
        patch.object(backfill, "build_finra_family", return_value={date(2026, 7, 1): {"finra_margin_debt_usd": 1.0}}),
        patch.object(backfill, "build_nfci_family", return_value={date(2026, 7, 1): {"nfci_leverage": 1.0}}),
        patch.object(backfill, "build_liquidity_family", return_value={date(2026, 7, 1): {"fed_walcl": 1.0}}),
        patch.object(backfill, "build_hy_oas_family", return_value={date(2026, 7, 1): {"hy_oas": 3.0}}),
        patch.object(backfill, "build_bdc_family", return_value={date(2026, 7, 1): {"bdc_regime_c_probability": 0.2}}),
        patch.object(backfill, "validate_macro_rows"),
    ):
        backfill._build_macro_data_rows(
            "2026-07-22T10:00:00+00:00",
            start_override="2020-01-01",
            allow_partial=True,
        )

    assert call("NFCILEVERAGE", "1970-01-01", backfill.END_DATE) in fred_fetch.call_args_list


def test_macro_full_builder_fails_closed_but_daily_mode_degrades_one_family():
    failures = []
    fred_rows = [(date(2026, 7, 1), 1.0)]
    with (
        patch.object(backfill, "fetch_finra_margin", side_effect=RuntimeError("finra down")),
        patch.object(backfill, "fetch_fred_series", return_value=fred_rows),
        patch.object(backfill, "load_verified_archive", return_value=[]),
        patch.object(backfill, "merge_archive_with_fred", return_value=[]),
        patch.object(backfill, "_fetch_yfinance_close", return_value={"2026-07-01": 6000.0}),
        patch.object(backfill, "load_bdc_exports", return_value=[]),
        patch.object(
            backfill,
            "build_nfci_family",
            return_value={date(2026, 7, 1): {"nfci_leverage": 1.0}},
        ) as build_nfci,
        patch.object(backfill, "build_liquidity_family", return_value={}),
        patch.object(backfill, "build_hy_oas_family", return_value={}),
        patch.object(backfill, "build_bdc_family", return_value={}),
        patch.object(backfill, "build_macro_rows", return_value=[MACRO_DATA_COLUMNS]) as build_rows,
        patch.object(backfill, "validate_macro_rows"),
    ):
        rows = backfill._build_macro_data_rows(
            "2026-07-22T10:00:00+00:00",
            allow_partial=True,
            failures=failures,
        )

    assert "FINRA" in failures
    assert "liquidity family" in failures
    assert "NFCI family" not in failures
    assert rows == [MACRO_DATA_COLUMNS]
    build_nfci.assert_called_once()
    assert build_rows.call_args.kwargs["finra"] == {}

    with patch.object(backfill, "fetch_finra_margin", side_effect=RuntimeError("finra down")):
        with pytest.raises(RuntimeError, match="finra down"):
            backfill._build_macro_data_rows("2026-07-22T10:00:00+00:00")


def test_full_run_batch_writes_macro_data_through_existing_entrypoint():
    db_rows = [["date"], ["2026-07-21"]]
    market_rows = [["date"], ["2026-07-21"]]
    macro_rows = valid_macro_rows()
    sheets = {name: MagicMock(name=name) for name in ("DB", "MARKET_DATA", "MACRO_DATA")}

    with (
        patch.object(backfill, "_build_db_rows", return_value=db_rows),
        patch.object(backfill, "_build_market_data_rows", return_value=market_rows),
        patch.object(backfill, "_build_macro_data_rows", return_value=macro_rows),
        patch.object(backfill, "get_sheet", side_effect=lambda name: sheets[name]),
        patch.object(backfill, "get_or_create_sheet", return_value=sheets["MACRO_DATA"]),
        patch.object(backfill, "batch_write") as batch_write,
    ):
        backfill.run(
            dry_run=False,
            sheets={"DB", "MARKET_DATA", "MACRO_DATA"},
        )

    assert batch_write.call_args_list == [
        call(sheets["DB"], db_rows, dry_run=False),
        call(sheets["MARKET_DATA"], market_rows, dry_run=False),
        call(
            sheets["MACRO_DATA"],
            macro_rows,
            dry_run=False,
            column_types=MACRO_DATA_COLUMN_TYPES,
        ),
    ]


def test_default_backfill_keeps_macro_inert_and_builds_all_targets_before_writing():
    db_rows = [["date"], ["2026-07-21"]]
    market_rows = [["date"], ["2026-07-21"]]
    with (
        patch.object(backfill, "_build_db_rows", return_value=db_rows),
        patch.object(backfill, "_build_market_data_rows", return_value=market_rows),
        patch.object(backfill, "_build_macro_data_rows") as build_macro,
        patch.object(backfill, "get_sheet", return_value=MagicMock()),
        patch.object(backfill, "batch_write") as batch_write,
    ):
        backfill.run(dry_run=False)

    build_macro.assert_not_called()
    assert len(batch_write.call_args_list) == 2


def test_explicit_multi_sheet_backfill_builds_every_target_before_first_mutation():
    with (
        patch.object(backfill, "_build_db_rows", return_value=[["date"]]),
        patch.object(backfill, "_build_market_data_rows", return_value=[["date"]]),
        patch.object(backfill, "_build_macro_data_rows", side_effect=RuntimeError("macro source failed")),
        patch.object(backfill, "get_sheet") as get_sheet,
        patch.object(backfill, "batch_write") as batch_write,
    ):
        with pytest.raises(RuntimeError, match="macro source failed"):
            backfill.run(
                dry_run=False,
                sheets={"DB", "MARKET_DATA", "MACRO_DATA"},
            )

    get_sheet.assert_not_called()
    batch_write.assert_not_called()


def test_macro_only_backfill_creates_missing_target_at_installation_boundary():
    macro_rows = valid_macro_rows()
    macro_sheet = MagicMock()
    with (
        patch.object(backfill, "_build_macro_data_rows", return_value=macro_rows),
        patch.object(backfill, "get_or_create_sheet", return_value=macro_sheet) as get_or_create,
        patch.object(backfill, "get_sheet") as get_sheet,
        patch.object(backfill, "batch_write") as batch_write,
    ):
        backfill.run(dry_run=False, sheets={"MACRO_DATA"})

    get_or_create.assert_called_once_with(
        "MACRO_DATA",
        rows=max(100, len(macro_rows)),
        cols=len(MACRO_DATA_COLUMNS),
    )
    get_sheet.assert_not_called()
    batch_write.assert_called_once_with(
        macro_sheet,
        macro_rows,
        dry_run=False,
        column_types=MACRO_DATA_COLUMN_TYPES,
    )


def test_macro_only_backfill_does_not_build_or_rewrite_existing_tabs():
    macro_rows = valid_macro_rows()
    macro_sheet = MagicMock()
    with (
        patch.object(backfill, "_build_db_rows") as build_db,
        patch.object(backfill, "_build_market_data_rows") as build_market,
        patch.object(backfill, "_build_macro_data_rows", return_value=macro_rows),
        patch.object(backfill, "get_or_create_sheet", return_value=macro_sheet) as get_or_create,
        patch.object(backfill, "batch_write") as batch_write,
    ):
        backfill.run(dry_run=False, sheets={"MACRO_DATA"})

    build_db.assert_not_called()
    build_market.assert_not_called()
    get_or_create.assert_called_once_with(
        "MACRO_DATA",
        rows=max(100, len(macro_rows)),
        cols=len(MACRO_DATA_COLUMNS),
    )
    batch_write.assert_called_once_with(
        macro_sheet,
        macro_rows,
        dry_run=False,
        column_types=MACRO_DATA_COLUMN_TYPES,
    )


def test_macro_daily_total_source_outage_returns_empty_update_not_exception():
    failures = []
    with (
        patch.object(backfill, "fetch_finra_margin", side_effect=RuntimeError("offline")),
        patch.object(backfill, "fetch_fred_series", side_effect=RuntimeError("offline")),
        patch.object(backfill, "load_verified_archive", side_effect=RuntimeError("offline")),
        patch.object(backfill, "load_bdc_exports", side_effect=RuntimeError("offline")),
        patch.object(backfill, "_fetch_yfinance_close", return_value=[]),
    ):
        rows = backfill._build_macro_data_rows(
            "2026-07-22T10:00:00+00:00",
            start_override="2020-01-01",
            write_start="2026-03-24",
            end_date="2026-07-21",
            allow_partial=True,
            failures=failures,
        )

    assert set(failures) == {"FINRA", "CPIAUCSL", "NFCILEVERAGE", "WALCL", "WTREGEN", "RRPONTSYD", "BAMLH0A0HYM2 current", "BAMLH0A0HYM2 archive", "SPX/SPY", "BDC inbox"}
    assert rows == [MACRO_DATA_COLUMNS]


def test_daily_includes_existing_sparse_dates_so_failed_family_becomes_kept_prior():
    index = {column: position for position, column in enumerate(MACRO_DATA_COLUMNS)}
    existing_row: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    existing_row[0] = "2026-07-05"
    existing_row[index["bdc_regime_c_probability"]] = 0.32
    existing_row[index["source_status_json"]] = json.dumps({"bdc": "ok"})
    existing_row[index["calculation_version_json"]] = json.dumps({"bdc": "bdc_structured_scores_v1"})
    incoming = [
        MACRO_DATA_COLUMNS,
        ["2026-07-07", *([""] * (len(MACRO_DATA_COLUMNS) - 1))],
    ]

    expanded = backfill.include_existing_macro_dates(
        incoming,
        [MACRO_DATA_COLUMNS, existing_row],
        write_start="2026-03-24",
        end_date="2026-07-21",
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )
    placeholder = next(row for row in expanded[1:] if row[0] == "2026-07-05")
    merged = list(existing_row)
    reconciled = backfill.reconcile_macro_source_status(
        existing_row,
        placeholder,
        merged,
    )

    assert reconciled[index["bdc_regime_c_probability"]] == 0.32
    assert json.loads(reconciled[index["source_status_json"]])["bdc"] == "kept_prior"


def test_daily_skips_macro_when_activation_gate_is_disabled():
    db_rows = [["date"], ["2026-07-21"]]
    market_rows = [["date"], ["2026-07-21"]]
    market_sheet = MagicMock()
    market_sheet.get_all_values.return_value = [backfill.MARKET_DATA_HEADER]
    db_sheet = MagicMock()
    with (
        patch.object(backfill, "MACRO_DATA_DAILY_ENABLED", False, create=True),
        patch.object(backfill, "_latest_completed_daily_date", return_value="2026-07-21"),
        patch.object(backfill, "_build_db_rows", return_value=db_rows),
        patch.object(backfill, "_build_market_data_rows", return_value=market_rows),
        patch.object(backfill, "_build_macro_data_rows") as macro_builder,
        patch.object(backfill, "get_sheet", side_effect=lambda name: {
            "DB": db_sheet,
            "MARKET_DATA": market_sheet,
        }[name]),
        patch.object(backfill, "upsert_rows") as upsert_rows,
        patch("src.services.windowed_sheets.write_windowed_db_sheets", return_value=[]),
        patch("src.services.windowed_sheets.write_windowed_market_data_sheets", return_value=[]),
    ):
        result = backfill.run_daily(dry_run=False, lookback_days=5)

    assert result == {"status": "ok", "macro_failures": [], "window_failures": []}
    macro_builder.assert_not_called()
    db_sheet.get_all_values.assert_not_called()
    market_sheet.get_all_values.assert_called_once()  # schema read, no optional history read
    assert len(upsert_rows.call_args_list) == 2


@pytest.mark.parametrize("failures", [[], ["WALCL", "FINRA", "WALCL"]])
def test_daily_run_recomputes_120_day_macro_window_and_upserts_under_existing_flow(failures):
    db_rows = [["date"], ["2026-07-21"]]
    market_rows = [["date"], ["2026-07-21"]]
    macro_rows = valid_macro_rows()
    market_sheet = MagicMock()
    market_sheet.get_all_values.return_value = [backfill.MARKET_DATA_HEADER]
    macro_sheet = MagicMock()
    macro_sheet.get_all_values.return_value = [MACRO_DATA_COLUMNS]
    db_sheet = MagicMock()

    def build_macro(*args, **kwargs):
        kwargs["failures"].extend(failures)
        return macro_rows

    with (
        patch.object(backfill, "MACRO_DATA_DAILY_ENABLED", True),
        patch.object(backfill, "_latest_completed_daily_date", return_value="2026-07-21"),
        patch.object(backfill, "_build_db_rows", return_value=db_rows),
        patch.object(backfill, "_build_market_data_rows", return_value=market_rows),
        patch.object(backfill, "_build_macro_data_rows", side_effect=build_macro) as macro_builder,
        patch.object(
            backfill,
            "get_sheet",
            side_effect=lambda name: {
                "DB": db_sheet,
                "MARKET_DATA": market_sheet,
                "MACRO_DATA": macro_sheet,
            }[name],
        ),
        patch.object(backfill, "upsert_rows") as upsert_rows,
        patch("src.services.windowed_sheets.write_windowed_db_sheets", return_value=[]) as window_db,
        patch("src.services.windowed_sheets.write_windowed_market_data_sheets", return_value=[]) as window_market,
    ):
        result = backfill.run_daily(dry_run=False, lookback_days=5)

    assert result == {"status": "partial" if failures else "ok", "macro_failures": sorted(set(failures)), "window_failures": []}
    window_db.assert_not_called()
    window_market.assert_not_called()
    assert upsert_rows.call_args_list[0].args[:2] == (db_sheet, db_rows[1:])
    assert upsert_rows.call_args_list[1].args[:2] == (market_sheet, market_rows[1:])
    assert macro_builder.call_args.kwargs == {
        "start_override": "2020-03-15",
        "write_start": "2026-03-24",
        "end_date": "2026-07-21",
        "allow_partial": True,
        "failures": failures,
    }
    assert upsert_rows.call_args_list[2].args[:2] == (macro_sheet, macro_rows[1:])


@pytest.mark.parametrize("status, expected", [("partial", 2), ("ok", 0)])
@pytest.mark.parametrize("dry_run", [False, True])
def test_daily_cli_status_without_external_followup(monkeypatch, status, expected, dry_run):
    from src.scripts import run_daily as cli
    events = []
    monkeypatch.setattr(cli.sys, "argv", ["run_daily", *(["--dry-run"] if dry_run else ["--write"])])
    monkeypatch.setattr(cli, "FileLock", MagicMock())
    def daily(**kwargs):
        events.append("daily")
        return {"status": status, "macro_failures": ["FINRA"] if status == "partial" else [], "window_failures": []}
    monkeypatch.setattr(cli, "run_daily", daily)
    assert cli.main() == expected
    assert events == ["daily"]


def test_macro_status_marks_kept_prior_only_when_merge_preserved_family_value():
    index = {column: position for position, column in enumerate(MACRO_DATA_COLUMNS)}
    existing = [""] * len(MACRO_DATA_COLUMNS)
    incoming = [""] * len(MACRO_DATA_COLUMNS)
    merged = [""] * len(MACRO_DATA_COLUMNS)
    for row in (existing, incoming, merged):
        row[0] = "2026-07-10"
    existing[index["nfci_leverage"]] = 0.5
    merged[index["nfci_leverage"]] = 0.5
    incoming[index["source_status_json"]] = json.dumps({"nfci": "missing"})
    merged[index["source_status_json"]] = incoming[index["source_status_json"]]

    reconciled = backfill.reconcile_macro_source_status(existing, incoming, merged)

    assert json.loads(reconciled[index["source_status_json"]])["nfci"] == "kept_prior"


def test_macro_merge_replaces_or_retains_whole_family_never_frankenstein_cells():
    index = {column: position for position, column in enumerate(MACRO_DATA_COLUMNS)}
    existing: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    incoming: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    merged: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    for row in (existing, incoming, merged):
        row[0] = "2026-07-10"
    existing[index["nfci_leverage"]] = 0.5
    existing[index["nfci_leverage_delta_3m"]] = 0.2
    incoming[index["nfci_leverage"]] = 0.6
    incoming[index["source_status_json"]] = json.dumps({"nfci": "ok"})
    merged[index["nfci_leverage"]] = 0.6
    merged[index["nfci_leverage_delta_3m"]] = 0.2
    merged[index["source_status_json"]] = incoming[index["source_status_json"]]

    reconciled = backfill.reconcile_macro_source_status(existing, incoming, merged)

    assert reconciled[index["nfci_leverage"]] == 0.6
    assert reconciled[index["nfci_leverage_delta_3m"]] == ""


def test_macro_merge_uses_canonical_family_to_calculation_version_keys():
    index = {column: position for position, column in enumerate(MACRO_DATA_COLUMNS)}
    existing: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    incoming: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    merged: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    for row in (existing, incoming, merged):
        row[0] = "2026-07-10"
    existing[index["finra_margin_debt_usd"]] = 1.0
    existing[index["fed_walcl"]] = 1.0
    existing[index["calculation_version_json"]] = json.dumps(
        {"finra_margin": "OLD", "net_fed_liquidity": "OLD"}
    )
    incoming[index["finra_margin_debt_usd"]] = 2.0
    incoming[index["fed_walcl"]] = 2.0
    incoming[index["source_status_json"]] = json.dumps(
        {"finra": "retrospective_current_vintage", "liquidity": "retrospective_current_vintage"}
    )
    incoming[index["calculation_version_json"]] = json.dumps(
        {"finra_margin": "NEW", "net_fed_liquidity": "NEW"}
    )
    merged[:] = incoming

    reconciled = backfill.reconcile_macro_source_status(existing, incoming, merged)

    assert json.loads(reconciled[index["calculation_version_json"]]) == {
        "finra_margin": "NEW",
        "net_fed_liquidity": "NEW",
    }
