"""Export-specific safety contract; the real CLI passes no-write by default."""
from unittest.mock import MagicMock
import pytest


@pytest.mark.parametrize("write", [False, True])
def test_daily_cli_write_requires_explicit_flag(monkeypatch, write):
    from src.scripts import run_daily as cli
    monkeypatch.setattr(cli.sys, "argv", ["run_daily"] + (["--write"] if write else []))
    monkeypatch.setattr(cli, "FileLock", MagicMock())
    daily = MagicMock(return_value={"status": "ok", "macro_failures": [], "window_failures": []})
    monkeypatch.setattr(cli, "run_daily", daily)
    assert cli.main() == 0
    assert daily.call_args.kwargs["dry_run"] is (not write)
    assert not hasattr(cli, "refresh_market_stress")


@pytest.mark.parametrize("write", [False, True])
def test_backfill_cli_write_requires_explicit_flag(monkeypatch, write):
    from src.scripts import run_backfill as cli
    run = MagicMock(return_value=None)
    monkeypatch.setattr(cli, "run", run)
    assert cli.main(["--write"] if write else []) == 0
    assert run.call_args.kwargs["dry_run"] is (not write)


def test_missing_account_fails_before_authentication(monkeypatch):
    from src.services import google_sheets as sheets
    monkeypatch.setattr(sheets, "_client", None)
    monkeypatch.setattr(sheets.settings, "SPREADSHEET_ID", "")
    credentials = MagicMock()
    monkeypatch.setattr(sheets.Credentials, "from_service_account_file", credentials)
    with pytest.raises(ValueError, match="SPREADSHEET_ID"):
        sheets.get_sheet("DB")
    credentials.assert_not_called()
