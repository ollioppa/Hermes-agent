"""
Central computation layer for all derived/rolling metrics.

compute_all(df) is a pure function — no I/O, no API calls, fully testable.
Input:  pd.DataFrame with DB_COLUMNS as column names, sorted ascending by date.
Output: same DataFrame with all computed columns filled in.

Rolling windows use min_periods so early rows get NaN rather than raising.
NaN in source columns propagates naturally — never backfill with 0.

Note: compute_coverage_pcts() currently only creates placeholder columns
(oi_coverage_pct, liq_coverage_pct set to None). No real coverage calculation
is implemented yet.
"""

import json

import pandas as pd
import numpy as np

# ── Partial-window contract (OD-14) ────────────────────────────────
# Each min_periods=1 rolling metric maps to (source column, window). A row
# is "partial" for that metric when the trailing window holds fewer than
# `window` real observations. The value is still emitted (emit-but-marked),
# never suppressed and never treated as a full 7d/30d metric.
PARTIAL_WINDOW_METRICS = {
    "cb_premium_7d_usd": ("cb_premium_usd", 7),
    "cb_premium_30d_usd": ("cb_premium_usd", 30),
    "fng_7d_median": ("fear_greed", 7),
    "fng_30d_median": ("fear_greed", 30),
    "mvrv_30d_median": ("mvrv", 30),
    "funding_7d_pct": ("funding_daily_pct", 7),
    "funding_30d_pct": ("funding_daily_pct", 30),
    "liq_7d_total_usd": ("liq_daily_total_usd", 7),
    "liq_30d_total_usd": ("liq_daily_total_usd", 30),
    "liq_7d_long_pct": ("liq_daily_total_usd", 7),
    "liq_30d_long_pct": ("liq_daily_total_usd", 30),
}


def compute_200w_ma(btc_price: pd.Series) -> pd.Series:
    """Return the 200-week MA from exact UTC Sunday closes, carried to later days."""
    prices = btc_price.copy()
    prices.index = pd.DatetimeIndex(prices.index)
    sunday = prices[prices.index.weekday == 6]
    if sunday.empty:
        return pd.Series(index=prices.index, dtype=float)
    expected = pd.date_range(sunday.index.min(), sunday.index.max(), freq="W-SUN")
    weekly = sunday.reindex(expected)
    weekly_ma = weekly.rolling(200, min_periods=200).mean()
    return weekly_ma.reindex(prices.index, method="ffill")


# All thresholds in one place
THRESHOLDS = {
    "flex_signal_ratio_max": 200,  # MA200W ratio < 200 → "FREI", >= 200 → "GESPERRT"
    "mvrv_alarm": 3.0,
    "mstr_trend_window": 90,       # days for MSTR/BTC ratio trend regression
    "ma200w_window": 1400,         # 200 weeks × 7 days
    "ma200w_min_periods": 200,     # require at least 200 days before emitting MA
}


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all derived columns in-place on a date-ascending DataFrame.

    Expects raw columns to be present (NaN where data unavailable).
    Returns the same DataFrame with computed columns filled.
    """
    df = df.copy()
    df = df.sort_values("date").reset_index(drop=True)
    # One source row per date; absent days remain absent, never filled.
    df.index = pd.DatetimeIndex(pd.to_datetime(df["date"]))

    # ── CB Premium ─────────────────────────────────────────────
    both_prices = df["btc_coinbase_close"].notna() & df["btc_binance_close"].notna()
    df.loc[both_prices, "cb_premium_usd"] = (
        df.loc[both_prices, "btc_coinbase_close"] - df.loc[both_prices, "btc_binance_close"]
    ).round(2)
    df.loc[both_prices, "cb_premium_pct"] = (
        df.loc[both_prices, "cb_premium_usd"] / df.loc[both_prices, "btc_binance_close"] * 100
    ).round(4)

    df["cb_premium_7d_usd"] = (
        df["cb_premium_usd"].rolling("7D", min_periods=1).median().round(2)
    )
    df["cb_premium_30d_usd"] = (
        df["cb_premium_usd"].rolling("30D", min_periods=1).median().round(2)
    )

    # ── Fear & Greed rolling medians ───────────────────────────
    fg = df["fear_greed"].astype(float)
    df["fng_7d_median"] = fg.rolling("7D", min_periods=1).median().round(1)
    df["fng_30d_median"] = fg.rolling("30D", min_periods=1).median().round(1)

    # ── MVRV rolling median ────────────────────────────────────
    df["mvrv_30d_median"] = (
        df["mvrv"].rolling("30D", min_periods=1).median().round(4)
    )

    # ── OI % change ────────────────────────────────────────────
    oi = df["perp_oi_usd"]
    for days in (7, 30):
        # Exact calendar anchor, without pct_change's implicit forward fill.
        previous = oi.reindex(oi.index - pd.Timedelta(days=days)).set_axis(oi.index)
        df[f"perp_oi_{days}d_change_pct"] = (
            (oi / previous.replace(0, np.nan) - 1).mul(100).round(2)
        )

    # ── Funding rolling medians ────────────────────────────────
    fund = df["funding_daily_pct"]
    df["funding_7d_pct"] = fund.rolling("7D", min_periods=1).median().round(6)
    df["funding_30d_pct"] = fund.rolling("30D", min_periods=1).median().round(6)

    # ── Liquidation rolling windows ────────────────────────────
    liq_total = df["liq_daily_total_usd"]
    liq_long = df["liq_daily_long_usd"]

    df["liq_7d_total_usd"] = liq_total.rolling("7D", min_periods=1).sum().round(2)
    df["liq_30d_total_usd"] = liq_total.rolling("30D", min_periods=1).sum().round(2)

    liq_7d_long = liq_long.rolling("7D", min_periods=1).sum()
    liq_7d_total = liq_total.rolling("7D", min_periods=1).sum()
    mask_7 = liq_7d_total > 0
    df.loc[mask_7, "liq_7d_long_pct"] = (liq_7d_long[mask_7] / liq_7d_total[mask_7] * 100).round(2)

    liq_30d_long = liq_long.rolling("30D", min_periods=1).sum()
    liq_30d_total = liq_total.rolling("30D", min_periods=1).sum()
    mask_30 = liq_30d_total > 0
    df.loc[mask_30, "liq_30d_long_pct"] = (liq_30d_long[mask_30] / liq_30d_total[mask_30] * 100).round(2)

    # ── MA200W from exact UTC Sunday closes ──────────────────────
    btc_price = df["btc_coinbase_close"].fillna(df["btc_binance_close"])
    ma_input = pd.Series(btc_price.to_numpy(), index=pd.to_datetime(df["date"]))
    df["btc_200w_ma_usd"] = compute_200w_ma(ma_input).to_numpy().round(2)

    both_ma = df["btc_200w_ma_usd"].notna() & btc_price.notna()
    df.loc[both_ma, "btc_200w_ma_ratio_pct"] = (
        btc_price[both_ma] / df.loc[both_ma, "btc_200w_ma_usd"] * 100
    ).round(2)

    ratio_threshold = THRESHOLDS["flex_signal_ratio_max"]
    df.loc[df["btc_200w_ma_ratio_pct"].notna(), "flex_signal"] = df.loc[
        df["btc_200w_ma_ratio_pct"].notna(), "btc_200w_ma_ratio_pct"
    ].apply(lambda r: "FREI" if r < ratio_threshold else "GESPERRT")

    # ── MSTR/BTC ratio + 90d trend ────────────────────────────
    both_mstr = df["mstr_close"].notna() & btc_price.notna() & (btc_price > 0)
    df.loc[both_mstr, "mstr_btc_ratio"] = (
        df.loc[both_mstr, "mstr_close"] / btc_price[both_mstr]
    ).round(6)

    # Legacy trend used observation-count regression, not a defined calendar metric.
    # Hold it until a separately named, calendar-based return/trend contract is migrated.
    df["mstr_btc_90d_trend_pct"] = np.nan

    # ── Open-data contract markers (OD-8 BTC source, OD-14 partial) ──
    df = annotate_data_contracts(df)

    return df.reset_index(drop=True)


def annotate_data_contracts(df: pd.DataFrame) -> pd.DataFrame:
    """Write OD-8/OD-14 markers into source_status_json without new schema.

    - OD-8: `btc_ma_source` records whether the MA/ratio input used the canonical
      Coinbase close, the visible Binance fallback, or had no BTC price.
    - OD-14: `partial_windows` lists the emitted min_periods=1 rolling metrics
      whose trailing window is not yet full, so no consumer reads a short-window
      value as a full 7d/30d metric.

    Both markers ride the already persisted, already consumed source_status_json
    column; legacy rows without the keys stay fail-closed at the consumer.
    """
    n = len(df)
    if "source_status_json" in df.columns:
        raw_status = df["source_status_json"].tolist()
    else:
        raw_status = ["{}"] * n

    # OD-8: which BTC price fed the MA/ratio input, per row.
    coinbase_present = df["btc_coinbase_close"].notna().to_numpy()
    binance_present = df["btc_binance_close"].notna().to_numpy()
    ma_source = np.where(
        coinbase_present, "coinbase",
        np.where(binance_present, "binance_fallback", "missing"),
    )

    # OD-14: trailing observation counts per rolling metric.
    obs_counts = {}
    metric_values = {}
    for metric, (source_col, window) in PARTIAL_WINDOW_METRICS.items():
        if metric not in df.columns or source_col not in df.columns:
            continue
        obs_counts[metric] = (
            pd.Series(df[source_col].notna().to_numpy(), index=pd.to_datetime(df["date"]))
            .rolling(f"{window}D", min_periods=1).sum().to_numpy()
        )
        metric_values[metric] = df[metric].to_numpy()

    new_status = []
    for i in range(n):
        try:
            status = json.loads(raw_status[i] or "{}")
            if not isinstance(status, dict):
                status = {}
        except (TypeError, ValueError, json.JSONDecodeError):
            status = {}

        partials = sorted(
            metric
            for metric, (_source_col, window) in PARTIAL_WINDOW_METRICS.items()
            if metric in obs_counts
            and pd.notna(metric_values[metric][i])
            and obs_counts[metric][i] < window
        )
        status["partial_windows"] = partials
        status["btc_ma_source"] = str(ma_source[i])
        new_status.append(json.dumps(status, sort_keys=True))

    df["source_status_json"] = new_status
    return df


def compute_coverage_pcts(
    df: pd.DataFrame,
    n_oi_symbols: int,
    n_liq_symbols: int,
) -> pd.DataFrame:
    """
    Estimate data coverage as a fraction of expected symbols that returned data.

    This is a rough proxy — requires knowing how many symbols were queried vs how many
    returned non-zero values on a given day. Currently set as constants from settings.
    """
    df = df.copy()
    # OI coverage: number of symbols with data / total symbols queried
    # In practice set during fetch; here we expose the column for manual override
    if "oi_coverage_pct" not in df.columns:
        df["oi_coverage_pct"] = None
    if "liq_coverage_pct" not in df.columns:
        df["liq_coverage_pct"] = None
    return df
