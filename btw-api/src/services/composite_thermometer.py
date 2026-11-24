"""Pure, fail-closed implementation of ``composite_thermometer_v1``.

This module deliberately has no API or Google Sheets I/O.  Its input is a DB
DataFrame (or records coercible to one); its output is JSON-serializable.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from types import MappingProxyType
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd

from src.config.settings import OI_BASKET_ID, OI_SYMBOLS

SCORE_SCHEMA_VERSION = "composite_thermometer_v1"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


# The JSON file is the sole v1 component-contract source. Runtime output receives
# a detached copy, while this frozen in-process view prevents mutation by callers.
_COMPONENT_CONTRACTS_PATH = Path(__file__).with_name("component_contracts_v1.json")
_COMPONENT_CONTRACTS_V1 = _freeze(json.loads(_COMPONENT_CONTRACTS_PATH.read_text(encoding="utf-8")))
ACTIVE_COMPONENT_IDS = tuple(_COMPONENT_CONTRACTS_V1)


def component_contracts_for_snapshot() -> Dict[str, Any]:
    """Return a detached, JSON-serializable v1 contract projection."""
    return json.loads(json.dumps(_COMPONENT_CONTRACTS_V1, default=dict))


def validate_component_contracts(value: Any) -> bool:
    """Accept only the immutable v1 contract projection emitted by this module."""
    return value == component_contracts_for_snapshot()


FUNDING_DIAGNOSTIC = {
    "id": "funding",
    "status": "held",
    "reason_code": "held_no_documented_settlement_aggregation",
    "points": None,
}


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _status(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_iso_date(value: Any) -> Optional[str]:
    if isinstance(value, date):
        return value.isoformat()
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    return parsed.date().isoformat() if not pd.isna(parsed) else None


def score_mvrv(value: Any) -> Optional[int]:
    raw = _number(value)
    if raw is None or raw <= 0:
        return None
    if raw < 1.3:
        return 2
    if raw < 1.5:
        return 1
    if raw <= 2.5:
        return 0
    return -2


def score_fear_greed(value: Any) -> Optional[int]:
    raw = _number(value)
    if raw is None or not 0 <= raw <= 100:
        return None
    if raw < 15:
        return 2
    if raw < 25:
        return 1
    if raw <= 75:
        return 0
    return -2


def percentile_points(current: Any, reference: Iterable[Any]) -> Optional[int]:
    current_value = _number(current)
    values = [_number(value) for value in reference]
    if current_value is None or len(values) != 180 or any(value is None for value in values):
        return None
    percentile = sum(value <= current_value for value in values if value is not None) / 180
    if percentile <= 0.20:
        return 2
    if percentile <= 0.40:
        return 1
    if percentile <= 0.60:
        return 0
    if percentile <= 0.80:
        return -1
    return -2


def bucket_for_score(score: int) -> str:
    if not isinstance(score, int) or score < -8 or score > 8:
        raise ValueError("score must be an integer in [-8, 8]")
    if score >= 6:
        return "A"
    if score >= 3:
        return "B"
    if score >= 0:
        return "C"
    if score >= -3:
        return "D"
    return "E"


def _component(component_id: str, raw: Any, points: Optional[int], reason_code: Optional[str] = None) -> Dict[str, Any]:
    if points is None:
        return {
            "id": component_id,
            "contract_version": SCORE_SCHEMA_VERSION,
            "status": "unavailable",
            "raw": None if _number(raw) is None else _number(raw),
            "points": None,
            "reason_code": reason_code or "missing_raw_value",
        }
    return {
        "id": component_id,
        "contract_version": SCORE_SCHEMA_VERSION,
        "status": "available",
        "raw": _number(raw),
        "points": points,
        "reason_code": None,
    }


def _frame_by_date(records: Any) -> Dict[str, Mapping[str, Any]]:
    frame = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
    if "date" not in frame.columns:
        return {}
    result: Dict[str, Mapping[str, Any]] = {}
    for _, row in frame.iterrows():
        day = _as_iso_date(row.get("date"))
        if day is not None and day not in result:
            result[day] = row.to_dict()
    return result


def _calendar_window(rows: Mapping[str, Mapping[str, Any]], as_of: date) -> Tuple[Optional[List[Mapping[str, Any]]], Optional[str]]:
    window: List[Mapping[str, Any]] = []
    for offset in range(180, 0, -1):
        expected = (as_of - timedelta(days=offset)).isoformat()
        row = rows.get(expected)
        if row is None:
            return None, "missing_calendar_day_in_180d_window"
        window.append(row)
    return window, None


def _cb_component(rows: Mapping[str, Mapping[str, Any]], as_of: date) -> Dict[str, Any]:
    current = rows.get(as_of.isoformat())
    if current is None:
        return _component("cb_premium", None, None, "missing_raw_value")
    current_status = _status(current.get("source_status_json"))
    if current_status.get("coinbase") != "ok" or current_status.get("binance") != "ok":
        return _component("cb_premium", current.get("cb_premium_pct"), None, "source_status_not_ok")
    if _number(current.get("btc_binance_close")) is None or _number(current.get("btc_binance_close")) <= 0 or _number(current.get("btc_coinbase_close")) is None:
        return _component("cb_premium", current.get("cb_premium_pct"), None, "invalid_raw_value")
    window, error = _calendar_window(rows, as_of)
    if error:
        return _component("cb_premium", current.get("cb_premium_pct"), None, error)
    reference: List[Any] = []
    for row in window or []:
        status = _status(row.get("source_status_json"))
        if status.get("coinbase") != "ok" or status.get("binance") != "ok":
            return _component("cb_premium", current.get("cb_premium_pct"), None, "component_identity_mismatch")
        if _number(row.get("btc_binance_close")) is None or _number(row.get("btc_binance_close")) <= 0 or _number(row.get("btc_coinbase_close")) is None:
            return _component("cb_premium", current.get("cb_premium_pct"), None, "invalid_raw_value")
        reference.append(row.get("cb_premium_pct"))
    points = percentile_points(current.get("cb_premium_pct"), reference)
    return _component("cb_premium", current.get("cb_premium_pct"), points, "insufficient_180d_complete_window")


def _valid_oi_provenance(provenance: Any) -> Tuple[bool, str]:
    if not isinstance(provenance, dict):
        return False, "basket_provenance_missing"
    if provenance.get("basket_id") != OI_BASKET_ID:
        return False, "basket_identity_mismatch"
    if provenance.get("provider") != "coinalyze" or provenance.get("endpoint") != "/v1/open-interest-history" or provenance.get("interval") != "daily" or provenance.get("field") != "c" or provenance.get("convert_to_usd") is not True:
        return False, "basket_identity_mismatch"
    expected = provenance.get("expected_symbols")
    observed = provenance.get("observed_symbols")
    if expected != list(OI_SYMBOLS) or not isinstance(observed, list) or len(set(observed)) != len(observed) or set(observed) != set(OI_SYMBOLS):
        return False, "unexpected_or_missing_oi_symbols"
    if provenance.get("expected_symbol_count") != 9 or provenance.get("observed_symbol_count") != 9:
        return False, "unexpected_or_missing_oi_symbols"
    if _number(provenance.get("coverage_pct")) != 100.0:
        return False, "oi_coverage_not_100"
    return True, ""


def _oi_component(rows: Mapping[str, Mapping[str, Any]], as_of: date) -> Dict[str, Any]:
    current = rows.get(as_of.isoformat())
    if current is None:
        return _component("oi", None, None, "missing_raw_value")
    current_status = _status(current.get("source_status_json"))
    if current_status.get("oi") != "ok":
        return _component("oi", current.get("perp_oi_usd"), None, "source_status_not_ok")
    valid, reason = _valid_oi_provenance(current_status.get("oi_basket_v1"))
    if not valid:
        return _component("oi", current.get("perp_oi_usd"), None, reason)
    window, error = _calendar_window(rows, as_of)
    if error:
        return _component("oi", current.get("perp_oi_usd"), None, error)
    reference: List[Any] = []
    for row in window or []:
        status = _status(row.get("source_status_json"))
        if status.get("oi") != "ok":
            return _component("oi", current.get("perp_oi_usd"), None, "source_status_not_ok")
        valid, reason = _valid_oi_provenance(status.get("oi_basket_v1"))
        if not valid:
            return _component("oi", current.get("perp_oi_usd"), None, reason)
        reference.append(row.get("perp_oi_usd"))
    points = percentile_points(current.get("perp_oi_usd"), reference)
    return _component("oi", current.get("perp_oi_usd"), points, "insufficient_180d_complete_window")


def _threshold_component(component_id: str, row: Optional[Mapping[str, Any]], source_key: str, raw_key: str, scorer) -> Dict[str, Any]:
    if row is None:
        return _component(component_id, None, None, "missing_raw_value")
    status = _status(row.get("source_status_json"))
    if status.get(source_key) != "ok":
        return _component(component_id, row.get(raw_key), None, "source_status_not_ok")
    points = scorer(row.get(raw_key))
    reason = "invalid_raw_value" if _number(row.get(raw_key)) is not None and points is None else "missing_raw_value"
    return _component(component_id, row.get(raw_key), points, reason)


def build_daily_thermometer(records: Any, as_of_date: str) -> Dict[str, Any]:
    """Build one v1 daily object without I/O or fallback column selection."""
    try:
        as_of = date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        raise ValueError("as_of_date must be YYYY-MM-DD")
    rows = _frame_by_date(records)
    components = {
        "cb_premium": _cb_component(rows, as_of),
        "oi": _oi_component(rows, as_of),
        "mvrv": _threshold_component("mvrv", rows.get(as_of.isoformat()), "mvrv", "mvrv", score_mvrv),
        "fear_greed": _threshold_component("fear_greed", rows.get(as_of.isoformat()), "fear_greed", "fear_greed", score_fear_greed),
    }
    if tuple(components) != ACTIVE_COMPONENT_IDS:
        raise RuntimeError("active v1 component implementation drift")
    available = {name: value["points"] for name, value in components.items() if value["status"] == "available"}
    missing = [
        {"id": value["id"], "status": "unavailable", "reason_code": value["reason_code"]}
        for value in components.values() if value["status"] != "available"
    ]
    base: Dict[str, Any] = {
        "score_schema_version": SCORE_SCHEMA_VERSION,
        "as_of_date": as_of.isoformat(),
        "components": components,
        "component_contracts": component_contracts_for_snapshot(),
        "funding_diagnostic": dict(FUNDING_DIAGNOSTIC),
        "weekly_history": [],
    }
    if len(available) == 4:
        score = sum(available.values())
        base.update({"status": "complete", "score": {"value": score, "min": -8, "max": 8}, "bucket": bucket_for_score(score)})
    elif available:
        base.update({"status": "partial", "score": None, "bucket": None, "available_component_points": available, "missing_components": missing})
    else:
        base.update({"status": "unavailable", "score": None, "bucket": None, "available_component_points": {}, "missing_components": missing})
    return base


def build_unavailable_thermometer_snapshot(as_of: Optional[date] = None) -> Dict[str, Any]:
    """Build the complete v1 unavailable shape when no usable DB date exists."""
    components = {
        component_id: _component(component_id, None, None, "missing_db_date")
        for component_id in ACTIVE_COMPONENT_IDS
    }
    missing = [
        {"id": value["id"], "status": "unavailable", "reason_code": value["reason_code"]}
        for value in components.values()
    ]
    history_as_of = as_of or date.today()
    current_monday = history_as_of - timedelta(days=history_as_of.weekday())
    first_day = current_monday - timedelta(days=35)
    unavailable_days = {
        (first_day + timedelta(days=offset)).isoformat(): {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "status": "unavailable",
            "missing_components": missing,
        }
        for offset in range(42)
    }
    return {
        "score_schema_version": SCORE_SCHEMA_VERSION,
        "status": "unavailable",
        "reason_code": "missing_db_date",
        "components": components,
        "component_contracts": component_contracts_for_snapshot(),
        "funding_diagnostic": dict(FUNDING_DIAGNOSTIC),
        "score": None,
        "bucket": None,
        "available_component_points": {},
        "missing_components": missing,
        "weekly_history": build_weekly_history(unavailable_days, history_as_of.isoformat()),
    }


def build_weekly_history(daily_scores: Mapping[str, Mapping[str, Any]], as_of_date: str) -> List[Dict[str, Any]]:
    """Return current W-SUN slot plus six historical slots; a median requires seven complete v1 days."""
    as_of = date.fromisoformat(as_of_date)
    current_monday = as_of - timedelta(days=as_of.weekday())
    slots: List[Dict[str, Any]] = []
    for week_offset in range(7):
        week_start = current_monday - timedelta(days=7 * week_offset)
        dates = [week_start + timedelta(days=offset) for offset in range(7)]
        complete_values: List[int] = []
        missing_dates: List[str] = []
        missing_reasons: List[Dict[str, Any]] = []
        for day in dates:
            day_key = day.isoformat()
            daily = daily_scores.get(day_key)
            if daily and daily.get("score_schema_version") == SCORE_SCHEMA_VERSION and daily.get("status") == "complete" and isinstance(daily.get("score"), dict) and isinstance(daily["score"].get("value"), int):
                complete_values.append(daily["score"]["value"])
                continue
            missing_dates.append(day_key)
            for component in (daily or {}).get("missing_components", []):
                if isinstance(component, dict):
                    missing_reasons.append({"date": day_key, "component": component.get("id"), "reason_code": component.get("reason_code")})
        common = {
            "week_start": week_start.isoformat(),
            "week_end": dates[-1].isoformat(),
            "label": "median_of_complete_daily_scores",
            "complete_day_count": len(complete_values),
            "missing_dates": missing_dates,
            "missing_reasons": missing_reasons,
        }
        if len(complete_values) == 7:
            slots.append({**common, "status": "complete", "median": float(pd.Series(complete_values).median())})
        elif len(complete_values) == 6:
            slots.append({**common, "status": "partial", "median": float(pd.Series(complete_values).median())})
        else:
            slots.append({**common, "status": "unavailable", "median": None})
    return slots
