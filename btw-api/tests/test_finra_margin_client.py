import io
import zipfile
from datetime import date

import pytest

from src.clients import finra_margin


SHEET_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>Year-Month</t></is></c><c r="B1" t="inlineStr"><is><t>Debit Balances in Customers' Securities Margin Accounts</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>2025-12</t></is></c><c r="B2"><v>100.5</v></c></row>
    <row r="3"><c r="A3" t="inlineStr"><is><t>2026-01</t></is></c><c r="B3"><v>110.25</v></c></row>
  </sheetData>
</worksheet>
"""


def xlsx_bytes(xml: str = SHEET_XML, shared_xml: str | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as workbook:
        workbook.writestr("xl/worksheets/sheet1.xml", xml)
        if shared_xml is not None:
            workbook.writestr("xl/sharedStrings.xml", shared_xml)
    return output.getvalue()


def test_finra_url_is_named_and_parser_returns_monthly_debit_balances():
    assert finra_margin.FINRA_MARGIN_XLSX_URL == (
        "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
    )
    assert finra_margin.parse_finra_margin_xlsx(xlsx_bytes()) == [
        (date(2025, 12, 1), 100.5),
        (date(2026, 1, 1), 110.25),
    ]


SHARED_XML = """<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<si><t>Year-Month</t></si><si><r><t>Debit </t></r><r><t>Balances in Customers Accounts</t></r></si>
<si><t>2025-12</t></si><si><r><t>2026-</t></r><r><t>01</t></r></si></sst>"""
SHARED_SHEET = SHEET_XML
for index, text in enumerate(("Year-Month", "Debit Balances in Customers' Securities Margin Accounts", "2025-12", "2026-01")):
    SHARED_SHEET = SHARED_SHEET.replace(f't="inlineStr"><is><t>{text}</t></is>', f't="s"><v>{index}</v>')


def test_finra_shared_headers_months_and_rich_text():
    assert finra_margin.parse_finra_margin_xlsx(xlsx_bytes(SHARED_SHEET, SHARED_XML)) == [
        (date(2025, 12, 1), 100.5), (date(2026, 1, 1), 110.25),
    ]


@pytest.mark.parametrize("index", ["-1", "99", "oops", ""])
def test_finra_rejects_invalid_shared_index(index):
    bad = SHARED_SHEET.replace('<v>2</v>', f'<v>{index}</v>')
    with pytest.raises(ValueError, match="shared-string index"):
        finra_margin.parse_finra_margin_xlsx(xlsx_bytes(bad, SHARED_XML))


def test_finra_inline_rich_text_remains_supported():
    rich = SHEET_XML.replace("<t>Year-Month</t>", "<r><t>Year-</t></r><r><t>Month</t></r>")
    assert finra_margin.parse_finra_margin_xlsx(xlsx_bytes(rich)) == finra_margin.parse_finra_margin_xlsx(xlsx_bytes())


def test_finra_rejects_missing_shared_table():
    with pytest.raises(ValueError, match="shared-string index"):
        finra_margin.parse_finra_margin_xlsx(xlsx_bytes(SHARED_SHEET))


@pytest.mark.parametrize("target", ["worksheet", "shared"])
@pytest.mark.parametrize("unsafe", ["<!DOCTYPE x>", "<!ENTITY x 'boom'>", " " * 20_000_001], ids=["doctype", "entity", "oversize"])
def test_finra_xml_safety_applies_to_both_parts(target, unsafe):
    sheet, shared = (unsafe, SHARED_XML) if target == "worksheet" else (SHARED_SHEET, unsafe)
    with pytest.raises(ValueError, match="unsafe FINRA"):
        finra_margin.parse_finra_margin_xlsx(xlsx_bytes(sheet, shared))


def test_finra_parser_fails_closed_when_header_drifts():
    bad = SHEET_XML.replace("Year-Month", "Period")
    with pytest.raises(ValueError, match="header"):
        finra_margin.parse_finra_margin_xlsx(xlsx_bytes(bad))


def test_finra_parser_rejects_duplicate_months():
    duplicate = SHEET_XML.replace("2026-01", "2025-12")
    with pytest.raises(ValueError, match="duplicate"):
        finra_margin.parse_finra_margin_xlsx(xlsx_bytes(duplicate))
