from pathlib import Path
import json
import pytest

from opportunity_radar.transitions import ContractError


@pytest.mark.parametrize('stamp', ['', 'yesterday', '2026-09-09', '2026-09-09T05:00:00', None])
def test_snapshot_retrieved_at_requires_aware_timestamp(stamp):
    with pytest.raises(ContractError):
        MarketSnapshot('AAA', 'case', 1, '2026-09-08', stamp, 'USD', 'test', 'close')


@pytest.mark.parametrize('stamp', ['2026-09-09T05:00:00Z', '2026-09-09T07:00:00+02:00'])
def test_snapshot_retrieved_at_accepts_aware_timestamp(stamp):
    assert MarketSnapshot('AAA', 'case', 1, '2026-09-08', stamp, 'USD', 'test', 'close').retrieved_at == stamp


@pytest.mark.parametrize('failure', ['replace', 'partial-write'])
def test_reader_replace_failure_keeps_bytes_and_digest(tmp_path, monkeypatch, failure):
    import opportunity_radar.report as report
    radar = RadarDB(tmp_path / 'radar.db')
    radar.initialize()
    output = tmp_path / 'reader.md'
    report.render_change_only(radar, output)
    old = output.read_bytes()
    with radar.connect() as con:
        digest = con.execute("SELECT digest FROM report_state WHERE name='reader'").fetchone()[0]
    original = report.build_report
    monkeypatch.setattr(report, 'build_report', lambda db: original(db) + '\nchanged\n')
    def fail(*args, **kwargs):
        raise OSError('injected')
    if failure == 'replace':
        monkeypatch.setattr(Path, 'replace', fail)
    else:
        import tempfile
        original_tempfile = tempfile.NamedTemporaryFile
        def broken_file(*args, **kwargs):
            handle = original_tempfile(*args, **kwargs)
            original_write = handle.write
            def broken_write(body):
                original_write(body[:5])
                raise OSError('injected partial write')
            handle.write = broken_write
            return handle
        monkeypatch.setattr(tempfile, 'NamedTemporaryFile', broken_file)
    with pytest.raises(OSError, match='injected'):
        report.render_change_only(radar, output)
    assert output.read_bytes() == old
    with radar.connect() as con:
        assert con.execute("SELECT digest FROM report_state WHERE name='reader'").fetchone()[0] == digest
    assert sorted(p.name for p in tmp_path.glob('*.tmp')) == []

from opportunity_radar.db import RadarDB
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.report import _specific_lines, build_screening_section, render_change_only


REVIEW = {
    "evidence_as_of": "2026-07-16",
    "motor": "Optum and insurance operations normalize",
    "environment": "healthcare demand is durable; regulation is the main regime risk",
    "relative_strength": "cash generation must recover faster than peers",
    "expectation": "the market prices persistent margin damage",
    "asymmetry": "upside from normalization; downside from structural cost inflation",
    "counterpath": "cost pressure and regulation remain structural",
    "falsifier": "two reports without margin stabilization",
    "missing_to_ready": "next results confirm margin recovery",
    "moat_competition": "scale remains material but politically exposed",
    "cash_conversion": "operating cash flow must normalize",
    "balance_financing": "funding remains available",
    "capital_allocation": "capital return cannot mask operating weakness",
    "valuation": "compare normalized earnings yield with SPY opportunity cost",
    "margins": "operating margin path must stabilize",
    "dilution": "share count must not rise materially",
    "customer_economics": {
        "historical_path": "pre-regime weakness, special-regime masking and normalization tested",
        "growth_composition": "price, volume, share and mix separated",
        "customer_value": "price compared with customer utility and peers",
        "support_intensity": "promotions and financing direction documented",
        "margin_source_and_use": "margin funded service renewal rather than extraction alone",
        "rent_quality": "value creation and scarcity rent remain mixed",
        "normalization_test": "existing margin-stabilization falsifier under normal competition",
    },
}


def snap(symbol: str, role: str, price: float) -> MarketSnapshot:
    return MarketSnapshot(symbol, role, price, "2026-09-08", "2026-09-09T05:00:00Z", "USD", "test", "close")


def test_reader_is_smartphone_first_and_second_identical_render_is_silent(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    case_id = radar.add_case("UNH", "UnitedHealth Group", "stock", "XLV")
    ids = {
        "case": radar.record_snapshot(case_id, snap("UNH", "case", 400.84)),
        "spy": radar.record_snapshot(case_id, snap("SPY", "benchmark", 765.96)),
        "sector": radar.record_snapshot(case_id, snap("XLV", "sector", 167.13)),
    }
    radar.freeze_review(case_id, REVIEW, source_urls=["https://example.com/unh"], snapshot_ids=ids, immediate_investable=False)
    radar.add_watch_condition(case_id, "event", "Next results confirm margin recovery")
    radar.transition(case_id, "WATCH", "review complete")
    output = tmp_path / "radar.md"

    first = render_change_only(radar, output)
    second = render_change_only(radar, output)

    assert first is not None
    assert second is None
    assert "## READY" in first
    assert first.index("## READY") < first.index("## WATCH")
    assert "**UNH — WATCH**" in first
    assert "Fehlt: Next results confirm margin recovery" in first
    assert "Umfeld: healthcare demand is durable" in first
    assert "Relativ: cash generation must recover faster than peers" in first
    assert "Lokale Preisbewegung seit Review (ohne Dividenden/FX): vs SPY +0.00 pp · vs XLV +0.00 pp · 0 Kalendertage" in first
    assert "Quellenstand: 2026-07-16" in first
    assert "https://example.com/unh" in first
    assert "Aktiencheck:" in first
    assert "Kundenökonomie: value creation and scarcity rent remain mixed" in first
    assert "Margenherkunft/-verwendung: margin funded service renewal rather than extraction alone" in first
    assert "Ops" not in first
    assert output.read_text(encoding="utf-8") == first


def test_reader_keeps_legacy_stock_review_without_customer_economics_readable() -> None:
    legacy_review = {key: value for key, value in REVIEW.items() if key != "customer_economics"}

    lines = _specific_lines("stock", legacy_review)

    assert lines[-1] == "- Verwässerung: share count must not rise materially"
    assert not any("Kundenökonomie:" in line for line in lines)


def test_reader_renders_screening_candidates_and_manual_authority(tmp_path: Path) -> None:
    radar = RadarDB(tmp_path / "radar.sqlite3")
    radar.initialize()
    with radar.connect() as connection:
        cycle_id = connection.execute(
            "INSERT INTO screen_cycles(cycle_key,cohort_index,provider,status,as_of,completed_at) VALUES ('trend-normalization:v1:2026-09-10',0,'hf_amir_yahoo','COMPLETED','2026-09-10',CURRENT_TIMESTAMP)"
        ).lastrowid
        connection.execute(
            "INSERT INTO candidate_inbox(stable_identity,symbol,name,kind,region,mic,status,first_seen_cycle_id,last_seen_cycle_id,lane,metrics_json) VALUES (?,?,?,?,?,?,'OPEN',?,?,?,?)",
            ("US:AAA", "AAA", "AAA Corp", "stock", "US", "US", cycle_id, cycle_id, "TREND_NORMALIZATION", '{"run_month":"2026-02","first_entry_month":"2026-08","latest_date":"2026-09-08","latest_close":100.0,"current_trend":105.0,"current_ratio":0.95238,"trend_slope":4.2}'),
        )

    body = render_change_only(radar, tmp_path / "radar.md")
    assert body is not None
    assert "## SCREENING-INBOX" in body
    assert "Unvollständige Recherche: 1/10" in body
    assert "**AAA — TREND_NORMALIZATION**" in body
    assert "erste Research-Zone 2026-08" in body
    assert "Abstand 95.24 %" in body
    assert "WATCH, READY und Archiv bleiben manuelle Entscheidungen" in body
    with radar.connect() as connection:
        connection.execute(
            "INSERT INTO screen_cycles(cycle_key,cohort_index,provider,status,as_of,failure_reason) VALUES ('trend-normalization:v1:2026-10-02',0,'hf_amir_yahoo','FAILED','2026-10-02','missing current prices')"
        )
    failed_section = build_screening_section(radar)
    assert "Coverage: FAILED · Provider hf_amir_yahoo" in failed_section
    assert "Technischer Grund: missing current prices" in failed_section


def test_reader_and_watchdog_use_same_bound_latest_series(tmp_path: Path) -> None:
    from opportunity_radar.report import build_report
    from opportunity_radar.watchdog import _latest_case_metrics
    radar = RadarDB(tmp_path / "radar.sqlite3"); radar.initialize()
    payload = json.loads(Path("tests/fixtures/stock_case.json").read_text())
    payload.update(symbol="AD", name="Synthetic euro listing", immediate_investable=True)
    payload.pop("watch_condition")
    for value in payload["snapshots"].values(): value["price_date"] = "2026-10-02"
    payload["snapshots"]["case"].update(symbol="AD", price=31.5, currency="EUR",
        provider="yahoo_chart:AD.AS", semantics="unadjusted regular-session close")
    case_id = radar.import_case(payload)
    for day, price, currency, provider in [("2026-10-14", 32.0, "EUR", "yahoo_chart:AD.AS"),
                                            ("2026-10-15", 99.0, "USD", "nasdaq_info")]:
        radar.record_snapshot(case_id, MarketSnapshot("AD", "case", price, day, day+"T20:00:00Z", currency,
            provider, 'unadjusted regular-session close |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}'))
        for key in ("spy", "sector"):
            value = dict(payload["snapshots"][key], price_date=day)
            value["semantics"] += ' |units={"since":"2026-01-01","through":"2027-12-31","breaks":[],"source":"explicit test fixture"}'
            radar.record_snapshot(case_id, MarketSnapshot(**value))
    body = build_report(radar)
    assert "Kurs: 32.00 EUR · Kursstand 2026-10-14" in body
    assert "Referenz: 31.50 EUR · 2026-10-02" in body
    assert "$99" not in body and "99.00 USD" not in body
    with radar.connect() as connection:
        metric = _latest_case_metrics(connection, case_id)
    assert metric is not None
    assert metric["price"] == 32 and metric["currency"] == "EUR"
