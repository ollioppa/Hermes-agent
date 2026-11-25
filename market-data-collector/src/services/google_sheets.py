"""
Google Sheets read/write service.

Sheet convention (inherited from GAS originals):
  - Row 1  : header row
  - Row 2+ : data, newest date first (descending chronological)

Upsert logic:
  - Existing date row found → update only non-empty values (merge-safe)
  - No row for that date → insert in descending date order, without reordering existing rows

Merge-safe means: if a column already has a value in the sheet and the new
value is empty/None, the existing sheet value is preserved. This prevents
an API failure in one client from wiping a previously written value.
"""

import logging
import math
import gspread
from gspread.utils import DateTimeOption, ValueRenderOption
from google.oauth2.service_account import Credentials
from src.config import settings

logger = logging.getLogger("market_data_collector.sheets")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: gspread.Client | None = None


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        if not settings.SPREADSHEET_ID:
            raise ValueError("Live Sheets access requires SPREADSHEET_ID and a service-account file; see README.md")
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
    return _client


def get_sheet(sheet_name: str) -> gspread.Worksheet:
    client = _get_client()
    spreadsheet = client.open_by_key(settings.SPREADSHEET_ID)
    return spreadsheet.worksheet(sheet_name)


def get_or_create_sheet(
    sheet_name: str,
    *,
    rows: int = 100,
    cols: int = 50,
) -> gspread.Worksheet:
    """Return an existing worksheet or create it with the requested capacity."""
    client = _get_client()
    spreadsheet = client.open_by_key(settings.SPREADSHEET_ID)
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.info("Creating missing worksheet %s", sheet_name)
        return spreadsheet.add_worksheet(
            title=sheet_name,
            rows=max(1, rows),
            cols=max(1, cols),
        )


def get_sheet_by_id(spreadsheet_id: str, sheet_name: str) -> gspread.Worksheet:
    """Get a sheet from a specific spreadsheet ID (for windowed sheets).

    Creates the worksheet if it doesn't exist.
    """
    if not spreadsheet_id:
        raise ValueError(f"Spreadsheet ID not configured for {sheet_name}")
    client = _get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    # Try to get existing worksheet
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # Create if not found
        logger.info(f"Creating worksheet '{sheet_name}' in configured spreadsheet")
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=50)
        return worksheet


def read_all_values(sheet: gspread.Worksheet, *, unformatted: bool = False) -> list[list]:
    """Return all rows including header.

    Raw numeric values are opt-in so legacy merge and header callers retain
    Google Sheets display values. Date cells remain formatted strings for
    snapshot consumers that request raw numbers.
    """
    if unformatted:
        return sheet.get_all_values(
            value_render_option=ValueRenderOption.unformatted,
            date_time_render_option=DateTimeOption.formatted_string,
        )
    return sheet.get_all_values()


def read_last_n_rows(sheet: gspread.Worksheet, n: int) -> list[list]:
    """Return header + last n data rows (by sheet position = most recent)."""
    all_values = sheet.get_all_values()
    if not all_values:
        return []
    header = all_values[:1]
    data = all_values[1:]
    return header + data[:n]  # sheet is newest-first, so first n rows = most recent n days


def upsert_rows(
    sheet: gspread.Worksheet,
    rows: list[list],
    date_col_index: int = 0,
    start_col: int | None = None,
    end_col: int | None = None,
    dry_run: bool = False,
    merge_row_transform=None,
) -> None:
    """
    Upsert rows into sheet with merge protection.

    For existing rows: only writes cells where the new value is non-empty.
    For new rows: inserts after the last newer date, preserving existing row order.

    Optional start_col/end_col are 1-based sheet columns for legacy partial
    jobs. In that mode rows are shaped as [date, value_for_start_col, ...].
    """
    if not rows:
        return

    all_values = sheet.get_all_values()
    data_rows = all_values[1:] if len(all_values) > 1 else []

    date_to_row: dict[str, int] = {}
    for i, row in enumerate(data_rows):
        if row and len(row) > date_col_index:
            date_to_row[row[date_col_index]] = i + 2  # 1-based, row 1 = header

    # Resolve start_col/end_col once so both passes can use them
    if rows and start_col is not None:
        if end_col is None:
            end_col = start_col + len(rows[0]) - 2
        if end_col < start_col:
            raise ValueError("end_col must be >= start_col")

    updates = [r for r in rows if str(r[date_col_index]) in date_to_row]
    inserts = [r for r in rows if str(r[date_col_index]) not in date_to_row]
    # Keep deterministic insertion order; each position uses the current row layout.
    inserts_asc = sorted(inserts, key=lambda r: str(r[date_col_index]))

    if dry_run:
        for new_row in rows:
            logger.info("[dry-run] upsert %s → %s", str(new_row[date_col_index]), new_row)
        return

    batch_updates: list[dict[str, object]] = []
    for new_row in updates:
        date_val = str(new_row[date_col_index])

        if start_col is not None:
            target_values = list(new_row[1:])
            expected = end_col - start_col + 1
            if len(target_values) > expected:
                raise ValueError(
                    f"partial row for {date_val} has {len(target_values)} values, "
                    f"but target range only accepts {expected}"
                )
        else:
            target_values = []

        row_num = date_to_row[date_val]
        existing = list(data_rows[row_num - 2])
        target_len = end_col if start_col is not None else len(new_row)
        while len(existing) < target_len:
            existing.append("")

        if start_col is not None:
            merged = existing[:target_len]
            if date_col_index < len(merged):
                merged[date_col_index] = date_val
            for offset, new_val in enumerate(target_values):
                target_idx = start_col - 1 + offset
                if new_val is not None and new_val != "":
                    merged[target_idx] = new_val
        else:
            merged = []
            for i, new_val in enumerate(new_row):
                if new_val is None or new_val == "":
                    merged.append(existing[i] if i < len(existing) else "")
                else:
                    merged.append(new_val)

        if merge_row_transform is not None:
            merged = merge_row_transform(existing, new_row, merged)

        col_end = gspread.utils.rowcol_to_a1(1, len(merged))[:-1]
        # Partial jobs must not rewrite preceding values/formulas via display strings.
        col_start = gspread.utils.rowcol_to_a1(1, start_col)[:-1] if start_col else "A"
        write_values = merged[start_col - 1:] if start_col else merged
        batch_updates.append(
            {"range": f"{col_start}{row_num}:{col_end}{row_num}", "values": [write_values]}
        )
        logger.debug("Prepared merged update for row %d (%s)", row_num, date_val)

    if len(batch_updates) == 1:
        update = batch_updates[0]
        sheet.update(
            update["range"],
            update["values"],
            value_input_option="USER_ENTERED",
        )
        logger.debug("Applied one merged row update")
    elif batch_updates:
        sheet.batch_update(batch_updates, value_input_option="USER_ENTERED")
        logger.debug("Applied %d merged row updates in one request", len(batch_updates))

    for new_row in inserts_asc:
        date_val = str(new_row[date_col_index])

        if start_col is not None:
            target_values = list(new_row[1:])
            insert_len = max(end_col or 0, date_col_index + 1)
            insert_row = [""] * insert_len
            insert_row[date_col_index] = date_val
            for offset, new_val in enumerate(target_values):
                target_idx = start_col - 1 + offset
                insert_row[target_idx] = "" if new_val is None else new_val
        else:
            insert_row = new_row
        # Scan rather than bisect: legacy rows may already contain an inversion.
        # After the last newer/equal date adds no new adjacent date inversion
        # and leaves the relative order of all existing rows untouched.
        insert_index = 2
        for i, row in enumerate(data_rows):
            if len(row) > date_col_index and str(row[date_col_index]) >= date_val:
                insert_index = i + 3
        sheet.insert_row(insert_row, index=insert_index)
        data_rows.insert(insert_index - 2, insert_row)
        logger.debug("Inserted new row for %s", date_val)


def batch_write(
    sheet: gspread.Worksheet,
    rows: list[list],
    dry_run: bool = False,
    column_types: dict[str, str] | None = None,
) -> None:
    """
    Overwrite the entire sheet (header + all data rows) in one batch call.

    Used for backfill where we recompute everything from scratch.
    rows[0] must be the header row.
    """
    if not rows:
        return
    if dry_run:
        logger.info("[dry-run] batch_write: %d rows (including header)", len(rows))
        return
    number_formats = {
        "date": {"type": "DATE", "pattern": "yyyy-mm-dd"},
        "datetime": {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm:ss"},
        "number": {"type": "NUMBER", "pattern": "#,##0.000000"},
        "integer": {"type": "NUMBER", "pattern": "#,##0"},
        "text": {"type": "TEXT", "pattern": "@"},
        "json": {"type": "TEXT", "pattern": "@"},
    }
    if column_types is None:
        formats = [(0, 1, number_formats["date"]),
                   (1, 26, {"type": "NUMBER", "pattern": "#,##0.00"})]
    else:
        if list(column_types) != list(rows[0]):
            raise ValueError("column_types order must exactly match the batch header")
        unknown = set(column_types.values()) - (set(number_formats) | {"boolean"})
        if unknown:
            raise ValueError(f"Unsupported column types: {sorted(unknown)}")
        formats = [(i, i + 1, number_formats[kind])
                   for i, kind in enumerate(column_types.values()) if kind != "boolean"]

    # Build and validate everything before the only mutation. Explicit ExtendedValue
    # types preserve RAW semantics (including strings beginning with '=').
    row_data = []
    for row in rows:
        cells = []
        for value in row:
            if value is None or (isinstance(value, str) and value == ""):
                cells.append({})
                continue
            if isinstance(value, bool):
                entered = {"boolValue": value}
            elif isinstance(value, (int, float)):
                if not math.isfinite(value):
                    raise ValueError("batch_write requires finite numbers")
                entered = {"numberValue": value}
            elif isinstance(value, str):
                entered = {"stringValue": value}
            else:
                raise ValueError(f"Unsupported cell type: {type(value).__name__}")
            cells.append({"userEnteredValue": entered})
        row_data.append({"values": cells})

    target_rows = max(sheet.row_count, len(rows))
    target_cols = max(sheet.col_count, max(map(len, rows)),
                      26 if column_types is None else len(rows[0]))
    requests = []
    growth = {}
    if target_rows > sheet.row_count:
        growth["rowCount"] = target_rows
    if target_cols > sheet.col_count:
        growth["columnCount"] = target_cols
    if growth:
        requests.append({"updateSheetProperties": {
            "properties": {"sheetId": sheet.id, "gridProperties": growth},
            "fields": ",".join(f"gridProperties.{key}" for key in growth),
        }})
    # A range, unlike start, clears omitted old rows/columns in the same batch.
    requests.append({"updateCells": {
        "range": {"sheetId": sheet.id, "startRowIndex": 0, "startColumnIndex": 0,
                  "endRowIndex": target_rows, "endColumnIndex": target_cols},
        "rows": row_data, "fields": "userEnteredValue",
    }})
    for start, end, number_format in formats:
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet.id, "startColumnIndex": start, "endColumnIndex": end},
            "cell": {"userEnteredFormat": {"numberFormat": number_format}},
            "fields": "userEnteredFormat.numberFormat",
        }})
    # Rejected batches leave values intact; timeout commit state remains unknown.
    sheet.spreadsheet.batch_update({"requests": requests})
    if growth:
        # Spreadsheet batches do not refresh Worksheet's cached grid capacity.
        # Mirror only our confirmed growth; failures leave local metadata intact.
        sheet._properties["gridProperties"].update(growth)
    logger.info("batch_write: wrote %d rows to sheet", len(rows))
