from datetime import date
import requests

import pytest

from src.clients import macro_fred


class FakeResponse:
    def __init__(self, text: str):
        self.content = text.encode('utf-8')
        self._bytes = self.content

    def raise_for_status(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._bytes


@pytest.mark.parametrize("series_id", sorted(macro_fred.MACRO_FRED_SERIES))
def test_fetch_fred_series_uses_named_series_and_parses_only_numeric_rows(monkeypatch, series_id):
    seen = {}

    import requests
    def fake_get(url, params, timeout):
        seen["url"] = url
        seen['params'] = params
        seen["timeout"] = timeout
        return FakeResponse(
            f"observation_date,{series_id}\n"
            "2026-01-02,-0.25\n"
            "2026-01-09,.\n"
            "2026-01-16,-0.10\n"
        )

    monkeypatch.setattr(requests, 'get', fake_get)
    rows = macro_fred.fetch_fred_series(series_id, "2026-01-01", "2026-02-01", timeout=17)
    assert seen["url"] == macro_fred.FRED_GRAPH_CSV_URL
    assert seen["timeout"] == 17
    assert seen['params'] == dict(id=series_id, cosd='2026-01-01', coed='2026-02-01')
    assert rows == [(date(2026, 1, 2), -0.25), (date(2026, 1, 16), -0.10)]


@pytest.mark.parametrize("text, error", [
    ("observation_date,WALCL\n2026-01-01,bad\n", "invalid FRED row"),
    ("observation_date,WALCL\nnot-a-date,1\n", "invalid FRED row"),
])
def test_fetch_fred_series_rejects_invalid_rows(monkeypatch, text, error):
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: FakeResponse(text))
    with pytest.raises(ValueError, match=error):
        macro_fred.fetch_fred_series("WALCL", "2026-01-01", "2026-02-01")


def test_fetch_fred_series_raises_http_error_before_parsing(monkeypatch):
    response = FakeResponse("not CSV")
    def fail():
        raise requests.HTTPError("upstream failure")
    response.raise_for_status = fail
    monkeypatch.setattr(requests, "get", lambda url, params, timeout: response)
    with pytest.raises(requests.HTTPError):
        macro_fred.fetch_fred_series("WALCL", "2026-01-01", "2026-02-01")


def test_fetch_fred_series_fails_closed_on_schema_drift(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, params, timeout: FakeResponse("DATE,WRONG\n2026-01-01,1\n"),
    )

    with pytest.raises(ValueError, match="schema"):
        macro_fred.fetch_fred_series("WALCL", "2026-01-01", "2026-02-01")


def test_fetch_fred_series_fails_on_empty_numeric_history(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, params, timeout: FakeResponse("observation_date,WALCL\n2026-01-01,.\n"),
    )

    with pytest.raises(ValueError, match="no numeric"):
        macro_fred.fetch_fred_series("WALCL", "2026-01-01", "2026-02-01")
