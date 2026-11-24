import json
import runpy
import pytest
from datetime import date


def scanner():
    return runpy.run_path(str(REPO / 'scripts/run_trend_screening.py'))


def sample_history():
    member = UniverseMember('US:AAA', 'AAA', 'AAA', 'stock', 'US', 'US', 'USD', 'test')
    rows = [(date(y, 12, 31), float(10 * (y - 2018))) for y in range(2019, 2024)]
    rows += [(date(2024, 1, 31), 80.), (date(2024, 2, 29), 50.), (date(2024, 3, 15), 50.)]
    return member, rows


def test_scanner_stale_year_and_future_rejected():
    ns = scanner()
    member, rows = sample_history()
    compute = ns['compute_current_signals']
    assert compute([member], {'AAA': rows}, {'AAA': rows[-1]}, as_of=date(2024, 3, 20))
    assert not compute([member], {'AAA': rows}, {'AAA': rows[-1]}, as_of=date(2025, 3, 20))
    assert not compute([member], {'AAA': rows}, {'AAA': rows[-1]}, as_of=date(2024, 3, 1))


@pytest.mark.parametrize('latest,entry', [('2023-12-31', '2023-11'), ('2025-01-01', '2024-02'), ('2024-03-15', '2023-11'), ('2024-03-15', '2024-12')])
def test_direct_publish_rejects_invalid_dates(tmp_path, latest, entry):
    from opportunity_radar.db import RadarDB
    ns = scanner()
    member, rows = sample_history()
    signals = ns['compute_current_signals']([member], {'AAA': rows}, {'AAA': rows[-1]}, as_of=date(2024, 3, 20))
    signals[0].update(latest_date=latest, first_entry_month=entry)
    db = tmp_path / 'radar.db'
    with pytest.raises(ValueError):
        ns['publish'](RadarDB(db), signals, as_of=date(2024, 3, 20), source_revision='test')
    assert not db.exists()


def test_refresh_revision_bound_before_download(tmp_path, monkeypatch):
    ns = scanner()
    calls = []
    class API:
        def dataset_info(self, repo):
            calls.append('revision')
            return type('Info', (), {'sha': 'immutable-revision'})()
    monkeypatch.setitem(ns['refresh_prices'].__globals__, 'HfApi', API)
    monkeypatch.setitem(ns['refresh_prices'].__globals__, 'snapshot_download', lambda *a, **kw: calls.append(kw))
    assert ns['refresh_prices'](tmp_path, []) == 'immutable-revision'
    assert calls[0] == 'revision'
    assert calls[1]['revision'] == 'immutable-revision'


def test_failed_refresh_with_existing_cache_blocks_publish(tmp_path, monkeypatch):
    ns = scanner()
    member, _ = sample_history()
    path = tmp_path / 'AAA.csv'
    path.write_text('date,adjusted_close\n2024-03-15,50\n')
    import pandas as pd
    monkeypatch.setattr(ns['yf'], 'download', lambda *a, **kw: pd.DataFrame())
    errors = ns['refresh_global_prices'](tmp_path, [member])
    assert errors and 'AAA' in errors
    from opportunity_radar.db import RadarDB
    db = tmp_path / 'radar.db'
    with pytest.raises(ValueError, match='refresh'):
        ns['publish'](RadarDB(db), [], as_of=date(2024, 3, 20), source_revision='test', refresh_errors=errors)
    assert not db.exists()
    assert path.read_text() == 'date,adjusted_close\n2024-03-15,50\n'


def test_global_digest_changes_for_anchor_not_last_price(tmp_path):
    ns = scanner()
    member, _ = sample_history()
    path = tmp_path / 'AAA.csv'
    path.write_text('date,adjusted_close\n2023-12-31,40\n2024-03-15,50\n')
    first = ns['load_global_price_rows'](tmp_path, [member])[2]['global_snapshot_digest']
    path.write_text('date,adjusted_close\n2023-12-31,39\n2024-03-15,50\n')
    second = ns['load_global_price_rows'](tmp_path, [member])[2]['global_snapshot_digest']
    assert first != second


def test_scanner_artifact_replace_failure_keeps_old(tmp_path, monkeypatch):
    ns = scanner()
    old = tmp_path / 'summary.json'
    old.write_text('old')
    def fail(*a, **kw):
        raise OSError('replace injected')
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(OSError):
        ns['write_artifacts'](tmp_path, [], {}, [])
    assert old.read_text() == 'old'
    assert not list(tmp_path.glob('*.tmp'))
from pathlib import Path

from opportunity_radar.universe import UniverseMember, _is_spy_equity_candidate, _load_europe


REPO = Path(__file__).resolve().parents[1]


def test_spy_equity_candidate_rejects_cvr_independent_of_display_name() -> None:
    assert not _is_spy_equity_candidate(
        {"A": "CONTRA HOLOGIC INCORPO", "B": "2682320D", "C": "436CVR021", "H": "USD"}
    )
    assert not _is_spy_equity_candidate(
        {"A": "TPG INC", "B": "2602335D", "C": "436CVR021", "H": "USD"}
    )


def test_spy_equity_candidate_keeps_normal_us_equity() -> None:
    assert _is_spy_equity_candidate(
        {"A": "APPLE INC", "B": "AAPL", "C": "037833100", "H": "USD"}
    )


def test_exsa_athens_cash_market_has_stable_xath_identity(tmp_path: Path) -> None:
    exchange_map = json.loads((REPO / "config/screen_exchange_map.json").read_text(encoding="utf-8"))
    (tmp_path / "exchange-map-v1.json").write_text(json.dumps(exchange_map), encoding="utf-8")
    header = "Ticker,Name,Exchange,Asset Class,Market Currency"
    rows = ["ETE,NATIONAL BANK OF GREECE,Athens Exchange S.A. Cash Market,Equity,EUR"]
    rows.extend(f"X{i},Xetra member {i},Xetra,Equity,EUR" for i in range(579))
    (tmp_path / "exsa.csv").write_text(
        "Fund Holdings as of,\"24/Sept/2026\"\nignored\n" + header + "\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    members = _load_europe(tmp_path)

    assert members["XATH:ETE"].symbol == "ETE"
    assert members["XATH:ETE"].currency == "EUR"


def test_full_adjusted_history_replaces_old_anchors(tmp_path, monkeypatch):
    import pandas as pd
    ns = scanner()
    member, _ = sample_history()
    path = tmp_path / 'AAA.csv'
    path.write_text('date,adjusted_close\n2023-12-31,100\n2024-03-15,50\n')
    calls = []
    def download(*args, **kwargs):
        calls.append(kwargs)
        return pd.DataFrame({'Adj Close': [40., 50.]}, index=pd.to_datetime(['2023-12-31', '2024-03-15']))
    monkeypatch.setattr(ns['yf'], 'download', download)
    assert ns['refresh_global_prices'](tmp_path, [member]) == {}
    assert calls[0]['period'] == 'max'
    assert '2023-12-31,40.0' in path.read_text()
    assert '100' not in path.read_text()


@pytest.mark.parametrize('refresh', [False, True])
def test_main_cache_provenance_and_refresh_failure(tmp_path, monkeypatch, refresh):
    ns = scanner()
    g = ns['main'].__globals__
    member, rows = sample_history()
    old = tmp_path / 'old.csv'
    old.write_text('fixture')
    args = ['scanner', '--old-csv', str(old), '--global-root', str(tmp_path), '--as-of', '2024-03-20']
    if refresh:
        args.append('--refresh')
    monkeypatch.setattr(ns['sys'], 'argv', args)
    monkeypatch.setitem(g, 'ROOT', tmp_path)
    monkeypatch.setitem(g, 'download_current_universe', lambda *a: tmp_path)
    monkeypatch.setitem(g, 'load_universe_sources', lambda *a: [member])
    def forbidden(*a, **kw):
        raise AssertionError('remote revision queried for local cache')
    monkeypatch.setitem(g, 'HfApi', forbidden)
    monkeypatch.setitem(g, 'load_price_rows', lambda *a: ({'AAA': rows}, {'AAA': rows[-1]}, {}, []))
    monkeypatch.setitem(g, 'load_global_price_rows', lambda *a: ({}, {}, {'global_snapshot_digest': 'fixture'}))
    published = []
    monkeypatch.setitem(g, 'publish', lambda *a, **kw: published.append(kw))
    if refresh:
        monkeypatch.setitem(g, 'refresh_prices', lambda *a: 'bound-revision')
        import pandas as pd
        monkeypatch.setattr(ns['yf'], 'download', lambda *a, **kw: pd.DataFrame())
        # Supply a global member so the real refresh producer sees the cached file.
        global_member = UniverseMember('XETR:AAA', 'AAA', 'AAA', 'stock', 'EU', 'XETR', 'EUR', 'test')
        monkeypatch.setitem(g, 'load_universe_sources', lambda *a: [member, global_member])
        (tmp_path / 'AAA.DE.csv').write_text('date,adjusted_close\n2024-03-15,50\n')
        with pytest.raises(RuntimeError, match='refresh failed'):
            ns['main']()
        assert not published
        assert not (tmp_path / 'output').exists()
    else:
        assert ns['main']() == 0
        summary = json.loads((tmp_path / 'output/screening/2024-03-20/summary.json').read_text())
        assert summary['amir_revision'] is None
        first = published[-1]['source_revision']
        rows[0] = (rows[0][0], rows[0][1] + 1)
        assert ns['main']() == 0
        assert published[-1]['source_revision'] != first


def test_yahoo_symbol_uses_athens_suffix() -> None:
    namespace = runpy.run_path(str(REPO / "scripts/run_trend_screening.py"))
    athens_member = UniverseMember(
        stable_identity="XATH:ETE",
        symbol="ETE",
        name="NATIONAL BANK OF GREECE",
        kind="stock",
        region="EU",
        mic="XATH",
        currency="EUR",
        source="EXSA",
    )

    assert namespace["yahoo_symbol"](athens_member) == "ETE.AT"
