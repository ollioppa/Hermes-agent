import pandas as pd

from src.services.indicators import compute_200w_ma, compute_all


def test_200w_ma_uses_exact_sunday_closes_and_carries_to_next_days():
    sundays = pd.date_range("2020-01-05", periods=200, freq="W-SUN")
    dates = sundays.append(pd.DatetimeIndex([sundays[-1] + pd.Timedelta(days=1)]))
    prices = pd.Series(list(range(1, 201)) + [300], index=dates)

    result = compute_200w_ma(prices)

    assert result.loc[sundays[-1]] == 100.5
    assert result.loc[dates[-1]] == 100.5


def test_200w_ma_fails_closed_when_a_sunday_close_is_missing():
    sundays = pd.date_range("2020-01-05", periods=200, freq="W-SUN")
    prices = pd.Series(range(1, 201), index=sundays).drop(sundays[50])

    result = compute_200w_ma(prices)

    assert result.isna().all()


def test_legacy_mstr_trend_is_held_not_recomputed_from_observation_count():

    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "btc_coinbase_close": 100.0,
        "btc_binance_close": 100.0,
        "mstr_close": 10.0,
        "fear_greed": 50.0,
        "mvrv": 1.0,
        "perp_oi_usd": 1.0,
        "funding_daily_pct": None,
        "liq_daily_total_usd": None,
        "liq_daily_long_usd": None,
    })
    assert compute_all(df)["mstr_btc_90d_trend_pct"].isna().all()
