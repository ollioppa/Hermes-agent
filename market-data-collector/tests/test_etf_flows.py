from src.clients.etf_flows import parse_etf_inflows


CURRENT_JINA_TEXT = """Title: Farside Investors

Date
IBIT
FBTC
Total

11 Aug 2026
50.2
(4.1)
7.8

12 Aug 2026
(14.3)
-
(61.1)
"""


LEGACY_TABLE_TEXT = """| Date | IBIT | FBTC | Total |
| --- | --- | --- | --- |
| 11 Aug 2026 | 50.2 | (4.1) | 7.8 |
| 12 Aug 2026 | (14.3) | - | (61.1) |
"""


def test_parse_etf_inflows_reads_current_jina_line_layout():
    assert parse_etf_inflows(CURRENT_JINA_TEXT, "2026-08-11", "2026-08-12") == {
        "2026-08-11": 7_800_000.0,
        "2026-08-12": -61_100_000.0,
    }


def test_parse_etf_inflows_keeps_legacy_table_compatibility():
    assert parse_etf_inflows(LEGACY_TABLE_TEXT, "2026-08-11", "2026-08-12") == {
        "2026-08-11": 7_800_000.0,
        "2026-08-12": -61_100_000.0,
    }
