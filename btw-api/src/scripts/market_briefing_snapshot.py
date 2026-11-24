import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any

import pandas as pd

from src.config.settings import (
    MACRO_DATA_CONSUMER_ENABLED,
    MACRO_DATA_COLUMNS,
    MACRO_DATA_COLUMN_TYPES,
)
from src.services.macro_data import MACRO_FAMILY_VERSION_KEYS

from src.services.composite_thermometer import (
    FUNDING_DIAGNOSTIC,
    SCORE_SCHEMA_VERSION,
    build_daily_thermometer,
    build_unavailable_thermometer_snapshot,
    build_weekly_history,
)
from src.services.thermometer_display import render_signal_score
from src.services.google_sheets import get_sheet, read_all_values


DB_FALLBACKS = {
    "btc": ["btc_binance_close", "btc_coinbase_close"],
    "mstr": ["mstr_close"],
    "fear_greed": ["fear_greed"],
    "mvrv": ["mvrv"],
    "ma_200w": ["btc_200w_ma_usd"],
    "ma_ratio_pct": ["btc_200w_ma_ratio_pct"],
    "funding": ["funding_daily_pct"],
    "cb_premium": ["cb_premium_usd"],
    "oi": ["perp_oi_usd"],
    "liq_total": ["liq_daily_total_usd"],
    "liq_long_pct": ["liq_7d_long_pct"],
    "flex_signal": ["flex_signal"],
    "mstr_btc_ratio": ["mstr_btc_ratio"],
    "mstr_btc_90d": ["mstr_btc_90d_trend_pct"],
    "etf_flows": ["btc_etf_total_flow_usd_m"],
    "source_status": ["source_status_json"],
}


def sheet_to_df(sheet_name: str) -> pd.DataFrame:
    values = read_all_values(get_sheet(sheet_name), unformatted=True)
    header, rows = values[0], values[1:]
    df = pd.DataFrame(rows, columns=header)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df



def numericize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col == "date":
            continue
        try:
            out[col] = pd.to_numeric(out[col])
        except Exception:
            pass
    return out


def normalize_macro_types(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the explicit MACRO_DATA schema without coercing sparse booleans."""
    out = df.copy()

    def boolean_value(value: Any) -> bool | None:
        if value is None or value is pd.NA or value == "":
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if pd.isna(value):
                return None
            if value in (0, 1):
                return bool(value)
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise ValueError(f"invalid MACRO_DATA boolean value: {value!r}")

    for column in out.columns:
        column_type = MACRO_DATA_COLUMN_TYPES.get(column)
        if column_type == "boolean":
            out[column] = out[column].map(boolean_value).astype(object)
        elif column_type == "integer":
            numeric = pd.to_numeric(out[column], errors="coerce")
            out[column] = numeric.map(lambda value: None if pd.isna(value) else int(value)).astype(object)
        elif column_type == "number":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _with_display(thermometer: dict[str, Any]) -> dict[str, Any]:
    thermometer["display"] = {
        "renderer_version": "thermometer_v1_compact_render_v1",
        "signal_score_markdown": render_signal_score(thermometer),
    }
    return thermometer


def build_thermometer_snapshot(db: pd.DataFrame) -> dict[str, Any]:
    """Build the single versioned thermometer contract from raw DB rows.

    The score engine owns all component availability and provenance decisions;
    this consumer only selects the newest dated DB row and attaches the current
    W-SUN slot plus six retrospective weekly median slots. It never substitutes
    a fallback value.
    """
    if "date" not in db.columns:
        return _with_display(build_unavailable_thermometer_snapshot())
    frame = db.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"].notna()].copy()
    if frame.empty:
        return _with_display(build_unavailable_thermometer_snapshot())
    frame["date"] = frame["date"].dt.date.astype(str)
    as_of = max(frame["date"])
    as_of_date = pd.Timestamp(as_of).date()
    current_monday = as_of_date - timedelta(days=as_of_date.weekday())
    first_week_day = current_monday - timedelta(days=42)
    scoring_start = first_week_day - timedelta(days=180)
    scoring_frame = frame[
        (frame["date"] >= scoring_start.isoformat()) & (frame["date"] <= as_of)
    ].copy()
    current = build_daily_thermometer(scoring_frame, as_of)
    daily_scores = {
        day: build_daily_thermometer(scoring_frame, day)
        for day in sorted(set(scoring_frame["date"]))
        if first_week_day.isoformat() <= day <= as_of
    }
    current["weekly_history"] = build_weekly_history(daily_scores, as_of)
    return _with_display(current)



def first_present(row: pd.Series, names: list[str]) -> Any:
    for name in names:
        if name in row.index and pd.notna(row[name]) and row[name] != "":
            return row[name]
    return None



def _dated_rows_newest_first(df: pd.DataFrame) -> pd.DataFrame:
    """Order a reader copy by the canonical date column, ignoring undated rows.

    Stable ties preserve the first physical row; no recency is inferred within
    a date. Callers selecting daily observations deduplicate after filtering
    missing values, so previous means a distinct earlier observation date.
    """
    frame = df.copy()
    if "date" not in frame.columns:
        frame["date"] = pd.NaT
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame[frame["date"].notna()].sort_values(
        "date", ascending=False, kind="stable"
    )


def first_valid(df: pd.DataFrame, names: list[str]) -> tuple[Any, Any]:
    df = _dated_rows_newest_first(df)
    for name in names:
        if name in df.columns:
            s = df[["date", name]].copy()
            s = s[s[name].notna() & (s[name] != "")]
            if not s.empty:
                return s.iloc[0][name], s.iloc[0]["date"]
    return None, None



def weekly_comparison(
    df: pd.DataFrame,
    names: list[str],
    metric_class: str,
    weeks_back: int = 1,
) -> dict[str, Any]:
    """Compare the current calendar week with an exact prior calendar week."""
    if weeks_back < 1:
        raise ValueError("weeks_back must be >= 1")
    for name in names:
        if name not in df.columns:
            continue
        series = df[["date", name]].copy()
        series = series[series["date"].notna() & series[name].notna() & (series[name] != "")]
        if series.empty:
            continue
        series[name] = pd.to_numeric(series[name])
        series = series.sort_values("date").reset_index(drop=True)
        current_date = series.iloc[-1]["date"].normalize()
        current_start = current_date.to_period("W-SUN").start_time.normalize()
        previous_start = current_start - pd.Timedelta(days=7 * weeks_back)
        elapsed_days = (current_date - current_start).days
        previous_end = previous_start + pd.Timedelta(days=elapsed_days)
        previous_week_end = previous_start + pd.Timedelta(days=6)

        base = {
            "schema_version": 2,
            "metric_class": metric_class,
            "current_period": {"start": current_start, "end": current_date},
            "reference_period": {"start": previous_start, "end": previous_week_end if metric_class != "flow" else previous_end},
            "reference_available": False,
            "current": None,
            "reference": None,
            "reference_date": None,
            "delta_abs": None,
            "delta_pct": None,
        }
        current_window = series[(series["date"] >= current_start) & (series["date"] <= current_date)]
        previous_window = series[(series["date"] >= previous_start) & (series["date"] <= (previous_end if metric_class == "flow" else previous_week_end))]
        current_offsets = sorted((current_window["date"].dt.normalize() - current_start).dt.days.unique().tolist())
        reference_offsets = sorted((previous_window["date"].dt.normalize() - previous_start).dt.days.unique().tolist())
        base.update({
            "current_end_date": current_date,
            "observed_current_offsets": current_offsets,
            "observed_reference_offsets": reference_offsets,
            "coverage_status": "calendar_unknown",
        })

        if metric_class == "flow":
            # A WTD sum is not comparable until the applicable trading/calendar
            # policy can prove coverage. Observed offsets are diagnostic only.
            base["reference_kind"] = "weekly_wtd_sum"
            return base
        else:
            base["reference_kind"] = "weekly_last" if weeks_back == 1 else "four_week_last" if weeks_back == 4 else f"{weeks_back}_week_last"
            if current_window.empty or previous_window.empty:
                return base
            current_row = current_window.iloc[-1]
            reference_row = previous_window.iloc[-1]
            current = float(current_row[name])
            reference = float(reference_row[name])
            base.update({"current": current, "reference": reference, "reference_date": reference_row["date"], "reference_available": True})

        delta_abs = current - reference
        base["delta_abs"] = delta_abs
        base["delta_pct"] = (delta_abs / reference * 100) if reference > 0 else None
        return base
    return {"schema_version": 2, "metric_class": metric_class, "reference_available": False, "reference": None, "delta_abs": None, "delta_pct": None}


def weekly_metric(df: pd.DataFrame, names: list[str], metric_class: str) -> dict[str, Any]:
    """Keep Daily values while adding exact 1W and 4W calendar comparisons."""
    metric = delta(df, names)
    metric["weekly_comparison"] = weekly_comparison(df, names, metric_class)
    metric["four_week_comparison"] = weekly_comparison(df, names, metric_class, weeks_back=4)
    return metric


def delta(df: pd.DataFrame, names: list[str]) -> dict[str, Any]:
    df = _dated_rows_newest_first(df)
    for name in names:
        if name in df.columns:
            s = df[["date", name]].copy()
            s = s[s[name].notna() & (s[name] != "")]
            s = s.drop_duplicates("date", keep="first")
            if len(s) >= 2:
                curr = float(s.iloc[0][name])
                prev = float(s.iloc[1][name])
                d_abs = curr - prev
                d_pct = (d_abs / prev * 100) if prev else None
                return {
                    "current": curr,
                    "previous": prev,
                    "current_date": s.iloc[0]["date"],
                    "previous_date": s.iloc[1]["date"],
                    "delta_abs": d_abs,
                    "delta_pct": d_pct,
                    "column": name,
                }
            if len(s) == 1:
                return {
                    "current": float(s.iloc[0][name]),
                    "previous": None,
                    "current_date": s.iloc[0]["date"],
                    "previous_date": None,
                    "delta_abs": None,
                    "delta_pct": None,
                    "column": name,
                }
    return {"current": None, "previous": None, "delta_abs": None, "delta_pct": None, "column": None}



def rows_with_source_status(
    df: pd.DataFrame, source: str, expected_status: str | set[str]
) -> pd.DataFrame:
    """Return only rows whose per-source contract explicitly matches allowed statuses.

    Legacy rows and malformed source metadata fail closed. This prevents a
    newly corrected source contract from silently reinterpreting old values.
    """
    if "source_status_json" not in df.columns:
        return df.iloc[0:0].copy()
    allowed_statuses = {expected_status} if isinstance(expected_status, str) else expected_status

    def matches(value: Any) -> bool:
        try:
            return json.loads(value).get(source) in allowed_statuses
        except (TypeError, ValueError, json.JSONDecodeError):
            return False

    return df[df["source_status_json"].map(matches)].copy()


def to_jsonable(v: Any):
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if isinstance(v, dict):
        return {k: to_jsonable(val) for k, val in v.items()}
    if isinstance(v, list):
        return [to_jsonable(x) for x in v]
    if v is pd.NA:
        return None
    if type(v).__module__.startswith("numpy") and hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and pd.isna(v):
        return None
    return v



def build_macro_snapshot(macro: pd.DataFrame) -> dict[str, Any]:
    """Resolve sparse Macro families from their latest non-empty Sheet row."""
    if "date" not in macro.columns:
        return {}
    frame = macro.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"].notna()].sort_values("date", ascending=False)
    specs = {
        "finra": {
            "value": "finra_margin_debt_usd",
            "effective_date": "finra_margin_date",
            "warning": "finra_rollover_warning",
        },
        "nfci": {
            "value": "nfci_leverage",
            "effective_date": "date",
            "warning": "nfci_leverage_warning",
        },
        "liquidity": {
            "value": "liquidity_tightening_component_count_3m",
            "effective_date": "date",
            "warning": "liquidity_2of3_3m_warning",
        },
        "hy_oas": {
            "value": "hy_oas",
            "effective_date": "date",
            "warning": "hy_oas_warning",
        },
        "bdc": {
            "value": "bdc_regime_c_probability",
            "effective_date": "bdc_as_of_date",
            "warning": None,
        },
    }
    snapshot: dict[str, Any] = {}
    for family, spec in specs.items():
        value_column = str(spec["value"])
        if value_column not in frame.columns:
            continue
        available = frame[
            frame[value_column].notna() & (frame[value_column] != "")
        ]
        if available.empty:
            continue
        row = available.iloc[0]
        effective_column = str(spec["effective_date"])
        effective_value = row.get(effective_column, row["date"])
        if pd.isna(effective_value) or effective_value == "":
            effective_value = row["date"]
        status = row.get(f"{family}_source_status")
        if not status and "source_status_json" in row.index:
            try:
                status = json.loads(row["source_status_json"] or "{}").get(family)
            except (TypeError, ValueError, json.JSONDecodeError):
                status = None
        metric_columns = {
            "finra": [
                column
                for column in MACRO_DATA_COLUMNS
                if column.startswith("finra_")
                or column in {"cpi_index", "sp500_close", "sp500_12m_high"}
            ],
            "nfci": [column for column in MACRO_DATA_COLUMNS if column.startswith("nfci_")],
            "liquidity": [
                column
                for column in MACRO_DATA_COLUMNS
                if column.startswith("fed_")
                or column.startswith("liquidity_")
                or column in {"walcl_delta_3m", "wtregen_delta_3m", "rrp_delta_3m"}
            ],
            "hy_oas": [column for column in MACRO_DATA_COLUMNS if column.startswith("hy_oas")],
            "bdc": [column for column in MACRO_DATA_COLUMNS if column.startswith("bdc_")],
        }[family]
        metrics: dict[str, Any] = {}
        for metric_column in metric_columns:
            if metric_column not in frame.columns:
                continue
            metric_rows = frame[
                frame[metric_column].notna() & (frame[metric_column] != "")
            ]
            if metric_rows.empty:
                continue
            metric_row = metric_rows.iloc[0]
            metric_effective_column = effective_column
            if family == "finra" and metric_column in {
                "sp500_close",
                "sp500_12m_high",
                "finra_sp500_near_high",
                "finra_rollover_warning",
                "finra_signal_authority",
            }:
                metric_effective_column = "date"
            metric_effective = metric_row.get(
                metric_effective_column, metric_row["date"]
            )
            if pd.isna(metric_effective) or metric_effective == "":
                metric_effective = metric_row["date"]
            metric_status = None
            metric_version = None
            try:
                metric_status = json.loads(
                    metric_row.get("source_status_json") or "{}"
                ).get(family)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            try:
                metric_version = json.loads(
                    metric_row.get("calculation_version_json") or "{}"
                ).get(MACRO_FAMILY_VERSION_KEYS[family])
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            metrics[metric_column] = {
                "value": to_jsonable(metric_row[metric_column]),
                "sheet_date": to_jsonable(metric_row["date"]),
                "effective_date": to_jsonable(metric_effective),
                "source_status": metric_status,
                "calculation_version": metric_version,
            }
        family_snapshot: dict[str, Any] = {
            "current_value": row[value_column],
            "sheet_date": to_jsonable(row["date"]),
            "effective_date": to_jsonable(effective_value),
            "source_status": status,
            "value_column": value_column,
            "weekly_comparison": weekly_comparison(frame, [value_column], "level"),
            "metrics": metrics,
        }
        warning_column = spec.get("warning")
        if warning_column and warning_column in frame.columns:
            warning_rows = frame[
                frame[str(warning_column)].notna()
                & (frame[str(warning_column)] != "")
            ]
            if not warning_rows.empty:
                warning_row = warning_rows.iloc[0]
                family_snapshot["warning"] = warning_row[str(warning_column)]
                family_snapshot["warning_sheet_date"] = to_jsonable(warning_row["date"])
        snapshot[family] = family_snapshot
    return snapshot


def build_sector_snapshot(market: pd.DataFrame, as_of: str | None = None) -> dict:
    """Read stored closes for the last completed review week; never re-fetch prices."""
    from datetime import date, datetime, time
    from src.config.settings import SECTOR_SYMBOL_MAP
    from src.clients.market_sessions import session_close
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo('America/New_York'))
    issue = date.fromisoformat(as_of) if as_of else now.date()
    cutoff = datetime.combine(issue,time.max,tzinfo=now.tzinfo) if as_of else now
    friday = issue - timedelta(days=(issue.weekday() - 4) % 7)
    def anchor(day):
        while session_close(day) is None:
            day -= timedelta(days=1)
        return day
    end = anchor(friday)
    if session_close(end)>cutoff:
        friday -= timedelta(days=7)
        end = anchor(friday)
    start = anchor(friday-timedelta(days=7))
    result = {'status':'unavailable', 'start_date':start.isoformat(), 'end_date':end.isoformat(),
              'basis':'USD price return, no dividends; SPDR sector ETF proxies', 'sectors':{}, 'benchmark':None,
              'source':'Yahoo via existing btw_api MARKET_DATA; sector ETF proxies, SP500 price-index benchmark'}
    required = ['SP500', *SECTOR_SYMBOL_MAP.values()]
    if market.empty or 'date' not in market or any(c not in market for c in required):
        return result
    frame = market.copy()
    frame['date'] = pd.to_datetime(frame['date'], errors='coerce')
    frame = frame[frame['date'].dt.date <= end]
    # A holiday may move an anchor back, but missing sector rows must not erase a
    # real SP500 session and silently substitute an older reporting period.
    first, last = start, end
    result.update(start_date=first.isoformat(), end_date=last.isoformat())
    anchors = []
    for day in (first, last):
        matched = frame[frame['date'].dt.date == day]
        if len(matched) != 1:
            return result
        values = pd.to_numeric(matched.iloc[0][required], errors='coerce')
        if values.isna().any() or (values <= 0).any() or not all(__import__('math').isfinite(v) for v in values):
            return result
        anchors.append(values)
    a,b = anchors
    def metric(column, url):
        return {'start_close':float(a[column]), 'end_close':float(b[column]),
                'change_pct':float((b[column]/a[column]-1)*100), 'url':url}
    result['sectors'] = {column: dict(metric(column, 'https://finance.yahoo.com/quote/'+symbol+'/'),ticker=symbol) for symbol,column in SECTOR_SYMBOL_MAP.items()}
    result['benchmark'] = metric('SP500', 'https://finance.yahoo.com/quote/%5EGSPC/')
    result['status'] = 'ready'
    return result


def validate_daily_freshness(snapshot: dict, expected_date: str) -> None:
    """Require actual daily anchors, not score completeness or fetch time."""
    for path in (("db_date",), ("score", "as_of_date"),
                 ("indicators", "btc", "current_date"),
                 ("market_data", "BTC", "current_date")):
        value = snapshot
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        # Exact ISO equality also rejects missing, malformed and future dates.
        if not isinstance(value, str) or value != expected_date:
            raise ValueError(f"daily freshness: {'.'.join(path)} must be {expected_date}")


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Read-only Sheet-backed market snapshot')
    parser.add_argument('--sectors-only', action='store_true')
    parser.add_argument('--as-of', help='Sector review issue date YYYY-MM-DD')
    parser.add_argument('--require-current-daily', action='store_true',
                        help='Require closed Europe/Berlin yesterday for DB, score and BTC observations')
    args = parser.parse_args(argv or [])
    if args.require_current_daily and (args.sectors_only or args.as_of):
        parser.error('--require-current-daily cannot be combined with sector/historical options')
    if args.as_of and not args.sectors_only:
        parser.error('--as-of applies only with --sectors-only; existing BTC snapshot is not a historical replay')
    if args.sectors_only:
        print(json.dumps(build_sector_snapshot(numericize(sheet_to_df('MARKET_DATA')), args.as_of), ensure_ascii=False, indent=2))
        return
    db = numericize(sheet_to_df("DB"))
    market = numericize(sheet_to_df("MARKET_DATA"))
    macro = (
        normalize_macro_types(sheet_to_df("MACRO_DATA"))
        if MACRO_DATA_CONSUMER_ENABLED
        else pd.DataFrame()
    )

    dated_db = _dated_rows_newest_first(db)
    if dated_db.empty:
        raise ValueError("DB contains no valid dated rows")
    today_db = dated_db.iloc[0]
    dated_market = _dated_rows_newest_first(market)
    liq_db = rows_with_source_status(db, "liq", {"ok_usd_v2", "kept_prior"})

    source_status = first_present(today_db, DB_FALLBACKS["source_status"])
    try:
        source_status = json.loads(source_status) if source_status else {}
    except Exception:
        source_status = {"raw": source_status}

    snapshot = {
        "db_date": today_db["date"],
        "market_date": dated_market.iloc[0]["date"] if not dated_market.empty else None,
        "score": build_thermometer_snapshot(db),
        "indicators": {
            "btc": weekly_metric(db, DB_FALLBACKS["btc"], "level"),
            "mstr": weekly_metric(db, DB_FALLBACKS["mstr"], "level"),
            "fear_greed": weekly_metric(db, DB_FALLBACKS["fear_greed"], "level"),
            "mvrv": weekly_metric(db, DB_FALLBACKS["mvrv"], "level"),
            "btc_200w_ma_usd": weekly_metric(db, DB_FALLBACKS["ma_200w"], "level"),
            "btc_200w_ma_ratio_pct": weekly_metric(db, DB_FALLBACKS["ma_ratio_pct"], "level"),
            "cb_premium_usd": weekly_metric(db, DB_FALLBACKS["cb_premium"], "level"),
            "perp_oi_usd": weekly_metric(db, DB_FALLBACKS["oi"], "level"),
            **({
                "liq_daily_total_usd": weekly_metric(liq_db, DB_FALLBACKS["liq_total"], "flow"),
                "liq_7d_long_pct": weekly_metric(liq_db, DB_FALLBACKS["liq_long_pct"], "pre_windowed"),
            } if not liq_db.empty else {}),
            "mstr_btc_ratio": weekly_metric(db, DB_FALLBACKS["mstr_btc_ratio"], "level"),
            "btc_etf_total_flow_usd_m": weekly_metric(db, DB_FALLBACKS["etf_flows"], "flow"),
            "flex_signal": {"current": first_present(today_db, DB_FALLBACKS["flex_signal"]), "column": "flex_signal", "weekly_comparison": {"schema_version": 2, "metric_class": "display_only", "reference_available": False}},
        },
        "market_data": {
            col: weekly_metric(market, [col], "level") for col in [
                "BTC", "MSTR", "STRK", "STRF", "STRD", "STRC", "SP500", "NASDAQ100",
                "GOLD", "DXY", "Smartgrid_ETF", "WNUC_Euro", "5MVW_Euro", "PTC", "MSCI_World_Core"
            ] if col in market.columns
        },
        "macro": build_macro_snapshot(macro),
        "sectors": build_sector_snapshot(market),
        "source_status": source_status,
    }
    snapshot = to_jsonable(snapshot)
    if args.require_current_daily:
        expected_date = (datetime.now(ZoneInfo('Europe/Berlin')).date() - timedelta(days=1)).isoformat()
        try:
            validate_daily_freshness(snapshot, expected_date)
        except ValueError as exc:
            parser.error(str(exc))
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
