from unittest.mock import MagicMock, patch

import gspread
import pytest


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_atomic_batch_rejects_invalid_values_before_mutation(value):
    sheet = IsolatedWorksheet()
    sheet.values = [["old"]]
    with pytest.raises(ValueError):
        batch_write(sheet, [["header"], [value]])
    sheet.spreadsheet.batch_update.assert_not_called()
    assert sheet.values == [["old"]]


def test_atomic_batch_failure_and_smaller_raw_replacement():
    sheet = IsolatedWorksheet()
    old = [["old", "tail"], ["old-row"], ["last-row"]]
    sheet.values = old
    sheet.spreadsheet.batch_update.side_effect = RuntimeError("rejected")
    with pytest.raises(RuntimeError, match="rejected"):
        batch_write(sheet, [["new"]])
    assert sheet.values == old
    sheet.spreadsheet.batch_update.side_effect = sheet.apply_batch
    rows = [["2026-07-21", "=1+1", False, 12, 1.25, '{"a":1}', None, ""]]
    batch_write(sheet, rows)
    assert sheet.values == [rows[0][:-2] + ["", ""]]
    requests = sheet.spreadsheet.batch_update.call_args.args[0]["requests"]
    cells = requests[0]["updateCells"]["rows"][0]["values"]
    assert cells[1] == {"userEnteredValue": {"stringValue": "=1+1"}}
    assert cells[2] == {"userEnteredValue": {"boolValue": False}}
    assert cells[3] == {"userEnteredValue": {"numberValue": 12}}


def test_atomic_rejection_never_clears_existing_sheet():
    sheet = MagicMock()
    sheet.id, sheet.row_count, sheet.col_count = 17, 100, 26
    stored = [["old", "tail"], ["older"]]
    old = [row[:] for row in stored]
    sheet.clear.side_effect = stored.clear
    sheet.update.side_effect = RuntimeError("write rejected")
    sheet.spreadsheet.batch_update.side_effect = RuntimeError("write rejected")
    with pytest.raises(RuntimeError, match="write rejected"):
        batch_write(sheet, [["replacement"]])
    assert stored == old
    sheet.clear.assert_not_called()
    sheet.update.assert_not_called()
    sheet.resize.assert_not_called()
    sheet.format.assert_not_called()
    sheet.batch_format.assert_not_called()


def test_atomic_batch_growth_noop_and_type_validation():
    sheet = IsolatedWorksheet()
    sheet._properties["gridProperties"].update(rowCount=1, columnCount=1)
    sheet.server_grid.update(rowCount=1, columnCount=1)
    batch_write(sheet, [])
    batch_write(sheet, [["x"]], dry_run=True)
    for kinds in ({"wrong": "text"}, {"x": "unsupported"}):
        with pytest.raises(ValueError):
            batch_write(sheet, [["x"]], column_types=kinds)
    sheet.spreadsheet.batch_update.assert_not_called()
    batch_write(sheet, [["x"], [1]])
    requests = sheet.spreadsheet.batch_update.call_args.args[0]["requests"]
    assert requests[0]["updateSheetProperties"]["properties"]["gridProperties"] == {"rowCount": 2, "columnCount": 26}
    assert (sheet.row_count, sheet.col_count) == (2, 26)

from src.config.settings import MACRO_DATA_COLUMNS, MACRO_DATA_COLUMN_TYPES
from src.services import google_sheets
from src.services.google_sheets import batch_write, get_or_create_sheet, read_all_values, upsert_rows


class IsolatedWorksheet(gspread.Worksheet):
    def __init__(self, rows=100, cols=26):
        # Real gspread metadata/cache; only the remote transport is simulated.
        spreadsheet = MagicMock()
        super().__init__(spreadsheet, {
            "sheetId": 17, "title": "offline",
            "gridProperties": {"rowCount": rows, "columnCount": cols},
        }, spreadsheet_id="offline",
            client=MagicMock(spec=gspread.http_client.HTTPClient))
        self.server_grid = {"rowCount": rows, "columnCount": cols}
        self.values = []
        self.formats = []
        spreadsheet.batch_update.side_effect = self.apply_batch

    def get_all_values(self, **_kwargs):
        return [list(row) for row in self.values]

    def apply_batch(self, body):
        # Server changes MUST NOT auto-refresh Worksheet._properties.
        for request in body["requests"]:
            if "updateSheetProperties" in request:
                grid = request["updateSheetProperties"]["properties"]["gridProperties"]
                assert all(value >= self.server_grid[key] for key, value in grid.items())
                self.server_grid.update(grid)
            elif "updateCells" in request:
                update = request["updateCells"]
                assert update["fields"] == "userEnteredValue"
                bounds = update["range"]
                # Clear only the requested rectangle, retaining any uncovered tail.
                cells = {(r, c): value for r, row in enumerate(self.values)
                         for c, value in enumerate(row)}
                for r, c in list(cells):
                    if (bounds["startRowIndex"] <= r < bounds["endRowIndex"]
                            and bounds["startColumnIndex"] <= c < bounds["endColumnIndex"]):
                        del cells[r, c]
                for r, row in enumerate(update["rows"]):
                    for c, cell in enumerate(row["values"]):
                        cells[r, c] = next(iter(cell.get("userEnteredValue", {}).values()), "")
                height = max((r + 1 for r, c in cells), default=0)
                width = max((c + 1 for r, c in cells), default=0)
                self.values = [[cells.get((r, c), "") for c in range(width)]
                               for r in range(height)]
            else:
                self.formats.append(request["repeatCell"])


@pytest.mark.parametrize("replacement_shape", [(1, 1), (3, 27)])
def test_atomic_real_worksheet_grow_then_replace_clears_tail_without_shrink(replacement_shape):
    sheet = IsolatedWorksheet(rows=2, cols=26)
    batch_write(sheet, [["old"] * 30 for _ in range(4)])
    # Check the actual inherited gspread properties, not a fake auto-cache.
    assert (sheet.row_count, sheet.col_count) == (4, 30)
    rows, cols = replacement_shape
    replacement = [["new"] * cols for _ in range(rows)]
    batch_write(sheet, replacement)
    requests = sheet.spreadsheet.batch_update.call_args.args[0]["requests"]
    assert not any("updateSheetProperties" in request for request in requests)
    bounds = next(request["updateCells"]["range"] for request in requests if "updateCells" in request)
    assert (bounds["endRowIndex"], bounds["endColumnIndex"]) == (4, 30)
    assert sheet.values == replacement
    assert sheet.server_grid == sheet._properties["gridProperties"]
    assert sheet.spreadsheet.batch_update.call_count == 2


@pytest.mark.parametrize("error", [RuntimeError("rejected"), TimeoutError("unknown commit")])
def test_atomic_real_worksheet_failed_grow_preserves_cached_metadata(error):
    sheet = IsolatedWorksheet(rows=2, cols=26)
    sheet.values = [["old"]]
    before = dict(sheet._properties["gridProperties"])
    sheet.spreadsheet.batch_update.side_effect = error
    with pytest.raises(type(error), match=str(error)):
        batch_write(sheet, [["new"] * 30 for _ in range(4)])
    assert sheet._properties["gridProperties"] == before
    assert sheet.values == [["old"]]
    sheet.spreadsheet.batch_update.assert_called_once()

def test_get_or_create_sheet_creates_missing_target_with_requested_capacity():
    client = MagicMock()
    spreadsheet = client.open_by_key.return_value
    spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("MACRO_DATA")
    created = MagicMock()
    spreadsheet.add_worksheet.return_value = created

    with patch.object(google_sheets, "_get_client", return_value=client):
        result = get_or_create_sheet("MACRO_DATA", rows=9223, cols=52)

    assert result is created
    spreadsheet.add_worksheet.assert_called_once_with(
        title="MACRO_DATA",
        rows=9223,
        cols=52,
    )


def test_get_or_create_sheet_reuses_existing_target_without_duplicate():
    client = MagicMock()
    spreadsheet = client.open_by_key.return_value
    existing = spreadsheet.worksheet.return_value

    with patch.object(google_sheets, "_get_client", return_value=client):
        result = get_or_create_sheet("MACRO_DATA", rows=9223, cols=52)

    assert result is existing
    spreadsheet.add_worksheet.assert_not_called()


def test_upsert_batches_existing_row_updates_into_one_write_request():
    sheet = MagicMock()
    sheet.get_all_values.return_value = [
        ["date", "value"],
        ["2026-07-21", "old-1"],
        ["2026-07-20", "old-2"],
    ]
    sheet.row_values.side_effect = [
        ["2026-07-21", "old-1"],
        ["2026-07-20", "old-2"],
    ]

    upsert_rows(
        sheet,
        [["2026-07-21", "new-1"], ["2026-07-20", "new-2"]],
    )

    sheet.row_values.assert_not_called()
    sheet.update.assert_not_called()
    sheet.batch_update.assert_called_once_with(
        [
            {"range": "A2:B2", "values": [["2026-07-21", "new-1"]]},
            {"range": "A3:B3", "values": [["2026-07-20", "new-2"]]},
        ],
        value_input_option="USER_ENTERED",
    )


def test_isolated_macro_sheet_round_trip_preserves_header_width_types_and_values():
    sheet = IsolatedWorksheet()
    row: list[object] = [""] * len(MACRO_DATA_COLUMNS)
    row[0] = "2026-07-21"
    row[MACRO_DATA_COLUMNS.index("hy_oas")] = 2.69
    row[MACRO_DATA_COLUMNS.index("hy_oas_warning")] = False
    row[MACRO_DATA_COLUMNS.index("source_status_json")] = '{"hy_oas":"ok"}'
    rows = [MACRO_DATA_COLUMNS, row]

    batch_write(sheet, rows, column_types=MACRO_DATA_COLUMN_TYPES)
    readback = read_all_values(sheet, unformatted=True)

    assert sheet.col_count == 52
    assert readback == rows
    assert all(len(read_row) == 52 for read_row in readback)
    assert readback[1][MACRO_DATA_COLUMNS.index("hy_oas")] == 2.69
    assert readback[1][MACRO_DATA_COLUMNS.index("hy_oas_warning")] is False



def test_macro_batch_write_resizes_through_az_and_applies_typed_formats():
    sheet = MagicMock()
    sheet.col_count = 26
    sheet.row_count = 100
    sheet.id = 17
    rows = [
        MACRO_DATA_COLUMNS,
        ["2026-07-21", *([""] * (len(MACRO_DATA_COLUMNS) - 1))],
    ]

    batch_write(sheet, rows, column_types=MACRO_DATA_COLUMN_TYPES)

    sheet.resize.assert_not_called()
    sheet.clear.assert_not_called()
    sheet.update.assert_not_called()
    sheet.spreadsheet.batch_update.assert_called_once()
    requests = sheet.spreadsheet.batch_update.call_args.args[0]["requests"]
    assert requests[0]["updateSheetProperties"]["properties"]["gridProperties"] == {"columnCount": 52}
    formats = [request["repeatCell"] for request in requests if "repeatCell" in request]
    by_range = {}
    for entry in formats:
        col = gspread.utils.rowcol_to_a1(1, entry["range"]["startColumnIndex"] + 1)[:-1]
        assert entry["fields"] == "userEnteredFormat.numberFormat"
        by_range[f"{col}:{col}"] = entry["cell"]["userEnteredFormat"]
    assert by_range["A:A"]["numberFormat"]["type"] == "DATE"
    assert by_range["AB:AB"]["numberFormat"]["type"] == "NUMBER"
    assert by_range["AX:AX"]["numberFormat"]["type"] == "TEXT"
    assert by_range["AZ:AZ"]["numberFormat"]["type"] == "DATE_TIME"
    assert "N:N" not in by_range  # boolean column, preserved as native TRUE/FALSE


class UpsertWorksheet:
    """Stateful in-memory worksheet: catch shifted update targets, not just calls."""

    def __init__(self, values):
        self.values = [list(row) for row in values]
        self.calls = []

    def get_all_values(self):
        return [list(row) for row in self.values]

    def update(self, range_name, values, *, value_input_option):
        self.batch_update([{"range": range_name, "values": values}],
                          value_input_option=value_input_option)

    def batch_update(self, updates, *, value_input_option):
        assert value_input_option == "USER_ENTERED"
        self.calls.append("update")
        for update in updates:
            row, col = gspread.utils.a1_to_rowcol(update["range"].split(":")[0])
            target = self.values[row - 1]
            values = update["values"][0]
            target.extend([""] * max(0, col - 1 + len(values) - len(target)))
            target[col - 1:col - 1 + len(values)] = values

    def insert_row(self, values, *, index):
        self.calls.append("insert")
        self.values.insert(index - 1, list(values))


def test_upsert_historical_inserts_and_updates_keep_descending_positions():
    sheet = UpsertWorksheet([
        ["date", "value"], ["2026-11-20", "old20"],
        ["2026-11-02", "old02"], ["2026-10-30", "old30"],
    ])
    upsert_rows(sheet, [
        ["2026-11-23", "new23"], ["2026-11-01", "new01"],
        ["2026-11-20", "updated20"], ["2026-10-30", ""],
        ["2026-11-10", "new10"], ["2026-09-30", "new-oldest"],
    ])
    assert sheet.values == [
        ["date", "value"], ["2026-11-23", "new23"],
        ["2026-11-20", "updated20"], ["2026-11-10", "new10"],
        ["2026-11-02", "old02"], ["2026-11-01", "new01"],
        ["2026-10-30", "old30"], ["2026-09-30", "new-oldest"],
    ]
    assert sheet.calls == ["update", "insert", "insert", "insert", "insert"]


def test_upsert_preserves_existing_inversion_without_adding_adjacent_inversions():
    old = ["2026-11-20", "2026-11-02", "2026-10-30", "2026-08-01", "2026-08-13", "2026-07-31"]
    sheet = UpsertWorksheet([["date", "value"], *[[d, d] for d in old]])
    upsert_rows(sheet, [[d, "new"] for d in ["2026-11-23", "2026-11-01", "2026-08-10"]])
    dates = [row[0] for row in sheet.values[1:]]
    assert [d for d in dates if d in old] == old
    assert [(a, b) for a, b in zip(dates, dates[1:]) if a < b] == [("2026-08-01", "2026-08-13")]
    assert dates.index("2026-11-02") < dates.index("2026-11-01") < dates.index("2026-10-30")
    assert [row for row in sheet.values[1:] if row[0] in old] == [[d, d] for d in old]


def test_upsert_historical_partial_columns_preserve_formulas_and_transform():
    sheet = UpsertWorksheet([["date", "formula", "value"], ["2026-11-20", "=1+1", "old"], ["2026-10-30", "=2+2", "keep"]])
    seen = []
    def transform(existing, incoming, merged):
        seen.append(existing[0])
        merged[2] = "transformed"
        return merged
    upsert_rows(sheet, [["2026-11-01", 4], ["2026-11-20", 5]],
                start_col=3, end_col=3, merge_row_transform=transform)
    assert seen == ["2026-11-20"]
    assert sheet.values[1:] == [["2026-11-20", "=1+1", "transformed"], ["2026-11-01", "", 4], ["2026-10-30", "=2+2", "keep"]]
    assert sheet.calls == ["update", "insert"]


def test_upsert_nonzero_date_column_empty_sheet_and_dry_run():
    sheet = UpsertWorksheet([["value", "date"]])
    incoming = [["first", "2026-11-01"], ["last", "2026-11-23"]]
    upsert_rows(sheet, incoming, date_col_index=1, dry_run=True)
    assert sheet.calls == []
    upsert_rows(sheet, incoming, date_col_index=1)
    upsert_rows(sheet, [["middle", "2026-11-20"], ["updated", "2026-11-01"]], date_col_index=1)
    assert sheet.values == [["value", "date"], ["last", "2026-11-23"], ["middle", "2026-11-20"], ["updated", "2026-11-01"]]
