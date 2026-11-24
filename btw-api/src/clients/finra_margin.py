from __future__ import annotations

import io
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime


FINRA_MARGIN_XLSX_URL = (
    "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
)
_XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    inline = cell.find("x:is", _XML_NS)
    if inline is not None:
        return "".join(node.text or "" for node in inline.iterfind(".//x:t", _XML_NS)).strip()
    value = cell.find("x:v", _XML_NS)
    raw = value.text.strip() if value is not None and value.text is not None else ""
    if cell.get("t") == "s":
        try:
            index = int(raw)
            if index < 0:
                raise ValueError("negative index")
            return shared_strings[index].strip()
        except (ValueError, IndexError) as exc:
            raise ValueError("invalid FINRA shared-string index") from exc
    return raw


def parse_finra_margin_xlsx(blob: bytes) -> list[tuple[date, float]]:
    """Parse the fixed FINRA workbook contract and reject silent schema drift."""
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as workbook:
            xml = workbook.read("xl/worksheets/sheet1.xml")
            shared_xml = (workbook.read("xl/sharedStrings.xml")
                          if "xl/sharedStrings.xml" in workbook.namelist() else None)
        # Input is accepted only from the fixed FINRA HTTPS endpoint, but still
        # reject XML entity/DTD constructs and unreasonable expansion surfaces
        # before stdlib parsing (defusedxml is not a project dependency).
        for label, part in (("worksheet", xml), ("shared strings", shared_xml)):
            if part is not None and (len(part) > 20_000_000 or b"<!DOCTYPE" in part or b"<!ENTITY" in part):
                raise ValueError(f"unsafe FINRA {label} XML")
        root = ET.fromstring(xml)
        shared_strings = []
        if shared_xml is not None:
            shared_strings = [
                "".join(node.text or "" for node in item.iterfind(".//x:t", _XML_NS))
                for item in ET.fromstring(shared_xml).findall("x:si", _XML_NS)
            ]
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("invalid FINRA XLSX workbook") from exc

    sheet_data = root.find("x:sheetData", _XML_NS)
    if sheet_data is None:
        raise ValueError("FINRA XLSX schema missing sheetData")

    parsed_rows: list[dict[str, str]] = []
    for row in sheet_data.findall("x:row", _XML_NS):
        cells: dict[str, str] = {}
        for cell in row.findall("x:c", _XML_NS):
            ref = str(cell.get("r", ""))
            column = "".join(ch for ch in ref if ch.isalpha())
            if column:
                cells[column] = _cell_text(cell, shared_strings)
        if cells:
            parsed_rows.append(cells)
    if not parsed_rows:
        raise ValueError("FINRA XLSX contains no rows")

    header = parsed_rows[0]
    if header.get("A") != "Year-Month" or "Debit Balances" not in header.get("B", ""):
        raise ValueError(f"FINRA XLSX header mismatch: {header!r}")

    observations: list[tuple[date, float]] = []
    seen: set[date] = set()
    for row in parsed_rows[1:]:
        raw_month = row.get("A", "")
        raw_debit = row.get("B", "")
        if not raw_month and not raw_debit:
            continue
        try:
            month = datetime.strptime(raw_month, "%Y-%m").date().replace(day=1)
            debit = float(raw_debit.replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid FINRA margin row: {row!r}") from exc
        if month in seen:
            raise ValueError(f"duplicate FINRA margin month: {month.isoformat()}")
        seen.add(month)
        observations.append((month, debit))
    if not observations:
        raise ValueError("FINRA XLSX contains no numeric margin observations")
    return sorted(observations)


def fetch_finra_margin(timeout: int = 30) -> list[tuple[date, float]]:
    request = urllib.request.Request(
        FINRA_MARGIN_XLSX_URL,
        headers={"User-Agent": "btw_api/macro-data-v1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        blob = response.read()
    return parse_finra_margin_xlsx(blob)
