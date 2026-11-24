"""OD-15 client contracts for Coinalyze liquidation missingness."""

from unittest.mock import patch

from src.clients import coinalyze


def _candle(day: str, **values: float | None) -> dict:
    return {"t": coinalyze._to_unix(day), **values}


def test_missing_long_is_unknown_and_total_is_unknown():
    payload = [{"symbol": "BTCUSDT_PERP.A", "history": [_candle("2026-07-10", s=7.5)]}]

    with patch.object(coinalyze.settings, "LIQ_SYMBOLS", [m["symbol"] for m in payload]), patch.object(coinalyze, "_get_with_retry", return_value=payload):
        result = coinalyze.fetch_liquidations("2026-07-10", "2026-07-10")

    assert result == {
        "2026-07-10": {"long": None, "short": 7.5, "total": None}
    }


def test_null_short_is_unknown_and_total_is_unknown():
    payload = [{"symbol": "BTCUSDT_PERP.A", "history": [_candle("2026-07-10", l=2.5, s=None)]}]

    with patch.object(coinalyze.settings, "LIQ_SYMBOLS", [m["symbol"] for m in payload]), patch.object(coinalyze, "_get_with_retry", return_value=payload):
        result = coinalyze.fetch_liquidations("2026-07-10", "2026-07-10")

    assert result == {
        "2026-07-10": {"long": 2.5, "short": None, "total": None}
    }


def test_explicit_zero_is_preserved():
    payload = [{"symbol": "BTCUSDT_PERP.A", "history": [_candle("2026-07-10", l=0, s=0)]}]
    with patch.object(coinalyze.settings, "LIQ_SYMBOLS", [m["symbol"] for m in payload]), patch.object(coinalyze, "_get_with_retry", return_value=payload):
        result = coinalyze.fetch_liquidations("2026-07-10", "2026-07-10")
    assert result["2026-07-10"] == {"long": 0.0, "short": 0.0, "total": 0.0}


def test_both_missing_preserves_date_and_marks_all_unknown():
    payload = [{"symbol": "BTCUSDT_PERP.A", "history": [_candle("2026-07-10")] }]
    with patch.object(coinalyze.settings, "LIQ_SYMBOLS", [m["symbol"] for m in payload]), patch.object(coinalyze, "_get_with_retry", return_value=payload):
        result = coinalyze.fetch_liquidations("2026-07-10", "2026-07-10")
    assert result == {"2026-07-10": {"long": None, "short": None, "total": None}}


def test_partial_market_candle_makes_affected_side_and_total_unknown():
    payload = [{"symbol": "A", "history": [_candle("2026-07-10", l=2, s=3)]}, {"symbol": "B", "history": [_candle("2026-07-10", s=5)]}]
    with patch.object(coinalyze.settings, "LIQ_SYMBOLS", [m["symbol"] for m in payload]), patch.object(coinalyze, "_get_with_retry", return_value=payload):
        result = coinalyze.fetch_liquidations("2026-07-10", "2026-07-10")
    assert result == {"2026-07-10": {"long": None, "short": 8.0, "total": None}}
