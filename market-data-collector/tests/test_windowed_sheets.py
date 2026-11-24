"""
Unit tests for windowed_sheets module (30/90/180d rolling window filtering).
"""

import pytest


@pytest.mark.parametrize("writer,tab", [("db", "DB"), ("market_data", "MARKET_DATA")])
@pytest.mark.parametrize("boundary", ["get", "write"])
def test_window_failure_is_returned_and_next_window_continues(monkeypatch, writer, tab, boundary):
    from src.services import windowed_sheets as windows
    function = getattr(windows, f"write_windowed_{writer}_sheets")
    monkeypatch.setattr(windows, "WINDOWED_SHEETS_ENABLED", True)
    monkeypatch.setattr(windows, "WINDOWED_SHEET_CONFIG", {
        "30d": {"days": 30, "spreadsheet_id": "first"},
        "90d": {"days": 90, "spreadsheet_id": "second"}})
    get = MagicMock(side_effect=[RuntimeError("offline"), "second"] if boundary == "get" else ["first", "second"])
    write = MagicMock(side_effect=[RuntimeError("offline"), None] if boundary == "write" else None)
    monkeypatch.setattr(windows, "get_sheet_by_id", get)
    monkeypatch.setattr(windows, "batch_write", write)
    assert function([["date"], ["2026-05-01"]], "2026-05-01") == [f"30d:{tab}:write_failed"]
    assert get.call_count == 2
    assert write.call_args.args[0] == "second"


@pytest.mark.parametrize("name,tab", [("db", "DB"), ("market_data", "MARKET_DATA")])
def test_window_result_contract(monkeypatch, name, tab):
    from src.services import windowed_sheets as windows
    function = getattr(windows, f"write_windowed_{name}_sheets")
    get, write = MagicMock(), MagicMock()
    monkeypatch.setattr(windows, "get_sheet_by_id", get)
    monkeypatch.setattr(windows, "batch_write", write)
    monkeypatch.setattr(windows, "WINDOWED_SHEETS_ENABLED", False)
    assert function([], "2026-05-01") == []
    monkeypatch.setattr(windows, "WINDOWED_SHEETS_ENABLED", True)
    assert function([], "2026-05-01") == [f"*:{tab}:no_data"]
    assert function([], "2026-05-01", dry_run=True) == []
    rows = [["date"], ["2020-01-01"]]
    monkeypatch.setattr(windows, "WINDOWED_SHEET_CONFIG", {})
    assert function(rows, "2026-05-01") == [f"*:{tab}:not_configured"]
    monkeypatch.setattr(windows, "WINDOWED_SHEET_CONFIG", {"30d": {"days": 30, "spreadsheet_id": ""}})
    assert function(rows, "2026-05-01") == [f"30d:{tab}:not_configured"]
    assert function(rows, "2026-05-01", dry_run=True) == []
    get.assert_not_called()
    write.assert_not_called()
    monkeypatch.setattr(windows, "WINDOWED_SHEET_CONFIG", {"30d": {"days": 30, "spreadsheet_id": "offline"}})
    assert function(rows, "2026-05-01") == []
    assert write.call_args.args[1] == [["date"]]  # valid input, empty filtered window
from datetime import date
from unittest.mock import patch, MagicMock

from src.services.windowed_sheets import (
    _filter_rows_by_window,
    write_windowed_db_sheets,
    write_windowed_market_data_sheets,
)


class TestFilterRowsByWindow:
    """Test the core filtering logic."""

    def test_filter_rows_by_window_30d_basic(self):
        """Test 30-day window filters correctly."""
        data_rows = [
            ["2026-05-01", "val1"],
            ["2026-04-02", "val2"],
            ["2026-04-01", "val3"],  # Outside window (30d back from 2026-05-01 = 2026-04-02)
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 30, date_col_index=0)
        assert len(result) == 2
        assert result[0][0] == "2026-05-01"
        assert result[1][0] == "2026-04-02"

    def test_filter_rows_by_window_90d(self):
        """Test 90-day window."""
        data_rows = [
            ["2026-05-01", "val1"],
            ["2026-02-01", "val2"],  # Exactly 90 days back
            ["2026-01-31", "val3"],  # Outside window
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 90, date_col_index=0)
        assert len(result) == 2
        assert result[0][0] == "2026-05-01"
        assert result[1][0] == "2026-02-01"

    def test_filter_rows_by_window_boundaries_inclusive(self):
        """Test that both boundaries are inclusive."""
        # 30d window: 2026-04-02 to 2026-05-01
        data_rows = [
            ["2026-05-01", "end_inclusive"],  # Should be included
            ["2026-04-02", "start_inclusive"],  # Should be included
            ["2026-04-01", "outside"],  # Should be excluded
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 30, date_col_index=0)
        assert len(result) == 2
        assert result[0][0] == "2026-05-01"
        assert result[1][0] == "2026-04-02"

    def test_filter_rows_empty_input(self):
        """Test with empty data rows."""
        result = _filter_rows_by_window([], "2026-05-01", 30, date_col_index=0)
        assert result == []

    def test_filter_rows_malformed_date_skipped(self):
        """Test that malformed dates are skipped without crashing."""
        data_rows = [
            ["2026-05-01", "val1"],
            ["invalid-date", "val2"],  # Malformed
            ["2026-04-15", "val3"],
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 30, date_col_index=0)
        assert len(result) == 2
        assert result[0][0] == "2026-05-01"
        assert result[1][0] == "2026-04-15"

    def test_filter_rows_missing_date_column_skipped(self):
        """Test that rows with missing date column are skipped."""
        data_rows = [
            ["2026-05-01", "val1"],
            ["val2"],  # Missing date column
            ["2026-04-15", "val3"],
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 30, date_col_index=0)
        assert len(result) == 2
        assert result[0][0] == "2026-05-01"
        assert result[1][0] == "2026-04-15"

    def test_filter_rows_preserves_order(self):
        """Test that original order is preserved."""
        data_rows = [
            ["2026-05-01", "a"],
            ["2026-04-20", "b"],
            ["2026-04-10", "c"],
            ["2026-04-05", "d"],
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 30, date_col_index=0)
        assert len(result) == 4
        # Should be in same order as input
        assert [row[1] for row in result] == ["a", "b", "c", "d"]

    def test_filter_rows_single_day(self):
        """Test with days_back=1 (only one day)."""
        data_rows = [
            ["2026-05-01", "val1"],
            ["2026-04-30", "val2"],
        ]
        result = _filter_rows_by_window(data_rows, "2026-05-01", 1, date_col_index=0)
        assert len(result) == 1
        assert result[0][0] == "2026-05-01"

    def test_filter_rows_custom_date_column_index(self):
        """Test with date not in column 0."""
        data_rows = [
            ["2026-05-01", "val1", "extra"],
            ["name", "2026-04-15", "extra"],  # Date in column 1
            ["2026-04-01", "val3", "extra"],
        ]
        # Only filtering rows where column 1 has a valid date
        result = _filter_rows_by_window(data_rows, "2026-05-01", 30, date_col_index=1)
        assert len(result) == 1
        assert result[0][1] == "2026-04-15"


class TestWriteWindowedSheets:
    """Test the write functions (mocked to avoid real API calls)."""

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", False)
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_db_sheets_disabled(self, mock_logger):
        """Test that disabled windowed sheets are skipped."""
        write_windowed_db_sheets([["date"], ["2026-05-01"]], "2026-05-01", dry_run=False)
        mock_logger.info.assert_called()
        # Check that "disabled" message was logged
        calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("disabled" in str(call).lower() for call in calls)

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", True)
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_db_sheets_no_data(self, mock_logger):
        """Test with empty data."""
        write_windowed_db_sheets([], "2026-05-01", dry_run=False)
        mock_logger.warning.assert_called()

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", True)
    @patch("src.services.windowed_sheets.WINDOWED_SHEET_CONFIG", {
        "30d": {"days": 30, "spreadsheet_id": ""},  # Empty ID
        "90d": {"days": 90, "spreadsheet_id": ""},
        "180d": {"days": 180, "spreadsheet_id": ""},
    })
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_db_sheets_no_config(self, mock_logger):
        """Test when all spreadsheet IDs are not configured."""
        header = ["date", "col1", "col2"]
        data = [["2026-05-01", "val1", "val2"]]
        write_windowed_db_sheets([header] + data, "2026-05-01", dry_run=False)
        # Should log warnings for each unconfigured sheet
        warning_calls = [call for call in mock_logger.warning.call_args_list]
        assert len(warning_calls) >= 3

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", True)
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_db_sheets_dry_run(self, mock_logger):
        """Test dry-run mode (no actual writes)."""
        # Mock config with real spreadsheet ID
        with patch("src.services.windowed_sheets.WINDOWED_SHEET_CONFIG", {
            "30d": {"days": 30, "spreadsheet_id": "test-sheet-id"},
        }):
            header = ["date", "col1"]
            data = [["2026-05-01", "val1"]]
            write_windowed_db_sheets([header] + data, "2026-05-01", dry_run=True)
            # Should NOT call batch_write in dry-run mode (but no easy way to test without mocking batch_write)
            # Just verify that info log was called
            assert mock_logger.info.called

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", True)
    @patch("src.services.windowed_sheets.get_sheet_by_id")
    @patch("src.services.windowed_sheets.batch_write")
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_db_sheets_calls_batch_write(self, mock_logger, mock_batch_write, mock_get_sheet):
        """Test that batch_write is called with correct data."""
        mock_sheet = MagicMock()
        mock_get_sheet.return_value = mock_sheet

        with patch("src.services.windowed_sheets.WINDOWED_SHEET_CONFIG", {
            "30d": {"days": 30, "spreadsheet_id": "test-sheet-id"},
        }):
            header = ["date", "col1"]
            # 35 rows (5 more than 30 days) to test filtering
            data = [[f"2026-04-{(26 + i):02d}", f"val{i}"] for i in range(35)]
            write_windowed_db_sheets([header] + data, "2026-05-01", dry_run=False)

            # Verify batch_write was called
            assert mock_batch_write.called
            called_args = mock_batch_write.call_args[0]
            rows = called_args[1]
            # Should have header + ~30 data rows
            assert len(rows) > 1
            assert len(rows) <= 32  # Header + 31 rows for 30d window (inclusive)

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", True)
    @patch("src.services.windowed_sheets.get_sheet_by_id")
    @patch("src.services.windowed_sheets.batch_write")
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_market_data_sheets_calls_batch_write(self, mock_logger, mock_batch_write, mock_get_sheet):
        """Test that MARKET_DATA write also calls batch_write."""
        mock_sheet = MagicMock()
        mock_get_sheet.return_value = mock_sheet

        with patch("src.services.windowed_sheets.WINDOWED_SHEET_CONFIG", {
            "30d": {"days": 30, "spreadsheet_id": "test-sheet-id"},
        }):
            header = ["date", "btc", "mstr"]
            data = [[f"2026-04-{(26 + i):02d}", f"price{i}", f"mstr{i}"] for i in range(35)]
            write_windowed_market_data_sheets([header] + data, "2026-05-01", dry_run=False)

            assert mock_batch_write.called

    @patch("src.services.windowed_sheets.WINDOWED_SHEETS_ENABLED", True)
    @patch("src.services.windowed_sheets.get_sheet_by_id")
    @patch("src.services.windowed_sheets.batch_write")
    @patch("src.services.windowed_sheets.logger")
    def test_write_windowed_db_sheets_handles_exception(self, mock_logger, mock_batch_write, mock_get_sheet):
        """Test that exceptions during write are logged but don't crash."""
        mock_get_sheet.side_effect = Exception("API error")

        with patch("src.services.windowed_sheets.WINDOWED_SHEET_CONFIG", {
            "30d": {"days": 30, "spreadsheet_id": "test-sheet-id"},
        }):
            header = ["date", "col1"]
            data = [["2026-05-01", "val1"]]
            # Continue without raising, but propagate the failure to Daily.
            assert write_windowed_db_sheets([header] + data, "2026-05-01", dry_run=False) == ["30d:DB:write_failed"]

            # Error should be logged
            assert mock_logger.error.called
