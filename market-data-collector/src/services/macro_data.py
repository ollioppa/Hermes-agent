from __future__ import annotations

import calendar
import hashlib
import json
from collections import Counter
from bisect import bisect_right
from datetime import date, datetime
from typing import Iterable

from src.config.settings import MACRO_DATA_COLUMNS


def monthly_last(rows: Iterable[tuple[date, float]]) -> list[tuple[date, float]]:
    by_month: dict[tuple[int, int], tuple[date, float]] = {}
    for observation_date, value in rows:
        key = (observation_date.year, observation_date.month)
        if key not in by_month or observation_date > by_month[key][0]:
            by_month[key] = (observation_date, float(value))
    return [by_month[key] for key in sorted(by_month)]


def _has_contiguous_months(rows: list[tuple], index: int, lookback: int) -> bool:
    if index < lookback:
        return False
    window = rows[index - lookback : index + 1]
    return all(
        (right[0].year * 12 + right[0].month)
        - (left[0].year * 12 + left[0].month)
        == 1
        for left, right in zip(window, window[1:])
    )


def _has_contiguous_month_keys(
    keys: list[tuple[int, int]], index: int, lookback: int
) -> bool:
    if index < lookback:
        return False
    window = keys[index - lookback : index + 1]
    return all(
        (right[0] * 12 + right[1]) - (left[0] * 12 + left[1]) == 1
        for left, right in zip(window, window[1:])
    )


def _percentile_to_date(rows: list[tuple[date, float]], index: int) -> float:
    current = rows[index][1]
    values = [value for _, value in rows[: index + 1]]
    return round(100.0 * sum(value <= current for value in values) / len(values), 1)


def build_nfci_family(
    rows: Iterable[tuple[date, float]],
) -> dict[date, dict[str, object]]:
    raw = sorted((observation_date, float(value)) for observation_date, value in rows)
    monthly = monthly_last(raw)
    output: dict[date, dict[str, object]] = {
        observation_date: {"nfci_leverage": value}
        for observation_date, value in raw
    }
    delta_series: list[tuple[date, float]] = []
    for index, (observation_date, value) in enumerate(monthly):
        record: dict[str, object] = {"nfci_leverage": value}
        if _has_contiguous_months(monthly, index, 3):
            delta_value = round(value - monthly[index - 3][1], 6)
            delta_series.append((observation_date, delta_value))
            delta_index = len(delta_series) - 1
            percentile = _percentile_to_date(delta_series, delta_index)
            record.update(
                {
                    "nfci_leverage_delta_3m": delta_value,
                    "nfci_leverage_percentile": percentile,
                    "nfci_leverage_warning": bool(
                        delta_index >= 6 and percentile >= 85.0 and delta_value > 0
                    ),
                }
            )
        output[observation_date] = record
    return output


def build_liquidity_family(
    walcl_rows: Iterable[tuple[date, float]],
    tga_rows: Iterable[tuple[date, float]],
    rrp_rows: Iterable[tuple[date, float]],
) -> dict[date, dict[str, object]]:
    """Build the reviewed 3M component-agreement liquidity warning."""
    raw_walcl = sorted((d, float(value)) for d, value in walcl_rows)
    raw_tga = sorted((d, float(value)) for d, value in tga_rows)
    raw_rrp = sorted((d, float(value)) for d, value in rrp_rows)
    walcl = {(d.year, d.month): (d, value) for d, value in monthly_last(raw_walcl)}
    tga = {(d.year, d.month): (d, value) for d, value in monthly_last(raw_tga)}
    rrp = {(d.year, d.month): (d, value) for d, value in monthly_last(raw_rrp)}
    keys = sorted(set(walcl) & set(tga) & set(rrp))
    output: dict[date, dict[str, object]] = {}
    for observation_date, value in raw_walcl:
        output.setdefault(observation_date, {})["fed_walcl"] = value
    for observation_date, value in raw_tga:
        output.setdefault(observation_date, {})["fed_tga_wtregen"] = value
    for observation_date, value in raw_rrp:
        output.setdefault(observation_date, {})["fed_rrp_rpontsyd"] = value
    for index, key in enumerate(keys):
        observation_date = max(walcl[key][0], tga[key][0], rrp[key][0])
        record = output.setdefault(observation_date, {})
        if _has_contiguous_month_keys(keys, index, 3):
            previous = keys[index - 3]
            walcl_delta = round(walcl[key][1] - walcl[previous][1], 6)
            tga_delta = round(tga[key][1] - tga[previous][1], 6)
            rrp_delta = round(rrp[key][1] - rrp[previous][1], 6)
            tightening_count = sum(
                (walcl_delta < 0, tga_delta > 0, rrp_delta > 0)
            )
            record.update(
                {
                    "walcl_delta_3m": walcl_delta,
                    "wtregen_delta_3m": tga_delta,
                    "rrp_delta_3m": rrp_delta,
                    "liquidity_tightening_component_count_3m": tightening_count,
                    "liquidity_2of3_3m_warning": tightening_count >= 2,
                }
            )
        output[observation_date] = record
    return output


def _month_gap(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def _asof_index(
    rows: list[tuple[date, float]], target: date, max_gap_months: int
) -> int | None:
    index = bisect_right([d for d, _ in rows], target) - 1
    if index < 0 or _month_gap(rows[index][0], target) > max_gap_months:
        return None
    return index


def build_hy_oas_family(
    oas_rows: Iterable[tuple[date, float, str]],
    spx_rows: Iterable[tuple[date, float]],
) -> dict[date, dict[str, object]]:
    """Build the pre-registered V7 HY-OAS trough-reversal fields."""
    raw_oas = sorted(
        (observation_date, float(value), regime)
        for observation_date, value, regime in oas_rows
    )
    oas_by_month: dict[tuple[int, int], tuple[date, float, str]] = {}
    for observation_date, value, regime in raw_oas:
        key = (observation_date.year, observation_date.month)
        if key not in oas_by_month or observation_date > oas_by_month[key][0]:
            oas_by_month[key] = (observation_date, value, regime)
    oas = [oas_by_month[key] for key in sorted(oas_by_month)]
    spx = monthly_last(spx_rows)
    output: dict[date, dict[str, object]] = {
        observation_date: {
            "hy_oas": value,
            "hy_oas_source_regime": regime,
        }
        for observation_date, value, regime in raw_oas
    }
    segment_start = 0
    for index, (observation_date, value, regime) in enumerate(oas):
        if index > 0 and _month_gap(oas[index - 1][0], observation_date) != 1:
            segment_start = index
        record = output.setdefault(
            observation_date,
            {"hy_oas": value, "hy_oas_source_regime": regime},
        )
        percentile_start = max(segment_start, index - 59)
        percentile_values = [v for _, v, _ in oas[percentile_start : index + 1]]
        if len(percentile_values) >= 36:
            percentile = round(
                100.0 * sum(candidate <= value for candidate in percentile_values)
                / len(percentile_values),
                1,
            )
            trough_start = max(segment_start, index - 11)
            trough_date, trough_value, _ = min(
                oas[trough_start : index + 1], key=lambda row: (row[1], row[0])
            )
            months_since_trough = _month_gap(trough_date, observation_date)
            widening = round(value - trough_value, 6)
            spx_index = _asof_index(spx, observation_date, max_gap_months=2)
            spx_near_high = False
            if spx_index is not None:
                high_start = max(0, spx_index - 11)
                spx_high = max(v for _, v in spx[high_start : spx_index + 1])
                spx_near_high = bool(spx_high and spx[spx_index][1] >= 0.95 * spx_high)
            quality = (
                "strict_60m_authority"
                if len(percentile_values) >= 60
                else "dotcom_coverage_36m_warmup"
            )
            still_tight = percentile <= 33.3
            record.update(
                {
                    "hy_oas_percentile_60m": percentile,
                    "hy_oas_trough_value": round(trough_value, 6),
                    "hy_oas_months_since_trough": months_since_trough,
                    "hy_oas_widening_from_trough": widening,
                    "hy_oas_still_tight": still_tight,
                    "hy_oas_sp500_near_high": spx_near_high,
                    "hy_oas_warning": bool(
                        months_since_trough <= 6
                        and widening >= 0.35
                        and still_tight
                        and spx_near_high
                    ),
                    "hy_oas_quality_status": quality,
                }
            )
        output[observation_date] = record
    return output


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _had_recent_blowoff_12m(
    percentiles: list[float | None], index: int
) -> bool:
    recent = [
        value
        for value in percentiles[max(0, index - 11) : index + 1]
        if value is not None
    ]
    return bool(recent and max(recent) >= 80.0)


def build_finra_family(
    margin_rows: Iterable[tuple[date, float]],
    cpi_rows: Iterable[tuple[date, float]],
    spx_rows: Iterable[tuple[date, float]],
) -> dict[date, dict[str, object]]:
    """Build publication-lagged FINRA V6a rollover rows from current histories."""
    margin = monthly_last(margin_rows)
    cpi = monthly_last(cpi_rows)
    spx = monthly_last(spx_rows)
    real_margin: list[tuple[date, float, float]] = []
    for margin_date, margin_value in margin:
        cpi_index = _asof_index(cpi, margin_date, max_gap_months=2)
        if cpi_index is None or cpi[cpi_index][1] == 0:
            continue
        real_margin.append(
            (
                margin_date,
                margin_value,
                round(100.0 * margin_value / cpi[cpi_index][1], 6),
            )
        )

    growth: list[tuple[date, float]] = []
    for index in range(3, len(real_margin)):
        previous = real_margin[index - 3][2]
        if previous <= 0:
            continue
        value = round((real_margin[index][2] / previous) ** 4 - 1.0, 6)
        growth.append((real_margin[index][0], value))

    percentiles: list[float | None] = []
    for index, (_, growth_value) in enumerate(growth):
        start = max(0, index - 59)
        values = [value for _, value in growth[start : index + 1]]
        if len(values) < 24:
            percentiles.append(None)
        else:
            percentiles.append(
                round(100.0 * sum(value <= growth_value for value in values) / len(values), 1)
            )

    margin_by_date = {margin_date: (margin_value, real) for margin_date, margin_value, real in real_margin}
    output: dict[date, dict[str, object]] = {
        _add_months(margin_date, 1): {
            "finra_margin_date": margin_date.isoformat(),
            "finra_margin_debt_usd": margin_value,
            "finra_margin_source_status": "retrospective_current_vintage",
        }
        for margin_date, margin_value in margin
    }
    for index, (margin_date, growth_value) in enumerate(growth):
        percentile = percentiles[index]
        if percentile is None:
            continue
        signal_date = _add_months(margin_date, 1)
        had_recent_blowoff = _had_recent_blowoff_12m(percentiles, index)
        current_growth_negative = growth_value < 0
        spx_index = _asof_index(spx, signal_date, max_gap_months=2)
        spx_close: float | None = None
        spx_high: float | None = None
        spx_near_high = False
        if spx_index is not None:
            spx_close = spx[spx_index][1]
            high_start = max(0, spx_index - 11)
            spx_high = max(value for _, value in spx[high_start : spx_index + 1])
            spx_near_high = bool(spx_high and spx_close >= 0.95 * spx_high)
        margin_value, real_value = margin_by_date[margin_date]
        # V6a is the reviewed 24-observation sensitivity variant. Even where a
        # full 60-month window exists, the rule's authority remains reduced.
        authority = "short_warmup_sensitivity"
        cpi_index = _asof_index(cpi, margin_date, 2)
        if cpi_index is None:
            raise ValueError(f"CPI context disappeared for FINRA row {margin_date}")
        output[signal_date].update(
            {
                "cpi_index": cpi[cpi_index][1],
                "sp500_close": spx_close,
                "sp500_12m_high": spx_high,
                "finra_real_margin": real_value,
                "finra_real_margin_growth_3m_annualized": growth_value,
                "finra_growth_percentile_60m": percentile,
                "finra_had_recent_blowoff": had_recent_blowoff,
                "finra_current_growth_negative": current_growth_negative,
                "finra_sp500_near_high": spx_near_high,
                "finra_rollover_warning": bool(
                    had_recent_blowoff and current_growth_negative and spx_near_high
                ),
                "finra_signal_authority": authority,
            }
        )
    return output


def build_bdc_family(records: Iterable[dict[str, object]]) -> dict[date, dict[str, object]]:
    """Place BDC rows on known export availability dates; retain payload as-of."""
    output: dict[date, dict[str, object]] = {}
    field_map = {
        "stage1_credit_quality": "bdc_stage1_credit_quality",
        "stage2_wrapper_repricing": "bdc_stage2_wrapper_repricing",
        "stage3_funding_stress": "bdc_stage3_funding_stress",
        "stage4_credit_supply": "bdc_stage4_credit_supply",
        "stage5_macro_effects": "bdc_stage5_macro_effects",
        "stage6_feedback": "bdc_stage6_feedback",
        "regime_a_probability": "bdc_regime_a_probability",
        "regime_b_probability": "bdc_regime_b_probability",
        "regime_c_probability": "bdc_regime_c_probability",
        "status_code": "bdc_status_code",
        "source_status": "bdc_source_status",
    }
    for source in records:
        export_date = datetime.strptime(str(source["export_date"]), "%Y-%m-%d").date()
        row: dict[str, object] = {"bdc_as_of_date": str(source["bdc_as_of_date"])}
        row.update({target: source[key] for key, target in field_map.items()})
        output[export_date] = row
    return output


CALCULATION_VERSIONS = {
    "finra": ("finra_margin", "finra_blowoff_rollover_v6a"),
    "nfci": ("nfci_leverage", "nfci_delta_3m_v1"),
    "liquidity": ("net_fed_liquidity", "component_agreement_2of3_3m_v1"),
    "hy_oas": ("hy_oas", "hy_oas_trough_reversal_v7"),
    "bdc": ("bdc", "bdc_structured_scores_v1"),
}
MACRO_FAMILY_VERSION_KEYS = {
    family: version_key
    for family, (version_key, _) in CALCULATION_VERSIONS.items()
}
MACRO_FAMILY_COLUMNS = {
    "finra": tuple(
        column
        for column in MACRO_DATA_COLUMNS
        if column.startswith("finra_")
        or column in {"cpi_index", "sp500_close", "sp500_12m_high"}
    ),
    "nfci": tuple(column for column in MACRO_DATA_COLUMNS if column.startswith("nfci_")),
    "liquidity": tuple(
        column
        for column in MACRO_DATA_COLUMNS
        if column.startswith("fed_")
        or column.startswith("liquidity_")
        or column in {"walcl_delta_3m", "wtregen_delta_3m", "rrp_delta_3m"}
    ),
    "hy_oas": tuple(column for column in MACRO_DATA_COLUMNS if column.startswith("hy_oas")),
    "bdc": tuple(column for column in MACRO_DATA_COLUMNS if column.startswith("bdc_")),
}
MACRO_POPULATED_STATUSES = {
    "finra": {"retrospective_current_vintage", "kept_prior", "stale", "partial"},
    "nfci": {"retrospective_current_vintage", "kept_prior", "stale", "partial"},
    "liquidity": {"retrospective_current_vintage", "kept_prior", "stale", "partial"},
    "hy_oas": {"history_bridge", "kept_prior", "stale", "partial"},
    "bdc": {"ok", "shallow_accumulation", "kept_prior", "stale", "partial"},
}


def build_macro_rows(
    *,
    finra: dict[date, dict[str, object]],
    nfci: dict[date, dict[str, object]],
    liquidity: dict[date, dict[str, object]],
    hy_oas: dict[date, dict[str, object]],
    bdc: dict[date, dict[str, object]],
    updated_at_utc: str,
) -> list[list[object]]:
    """Form the wide descending union without filling unavailable source cells."""
    families = {
        "finra": finra,
        "nfci": nfci,
        "liquidity": liquidity,
        "hy_oas": hy_oas,
        "bdc": bdc,
    }
    all_dates: set[date] = set()
    for family in families.values():
        all_dates.update(family)
    if not all_dates:
        raise ValueError("MACRO_DATA build produced no dates")

    rows: list[list[object]] = [list(MACRO_DATA_COLUMNS)]
    for observation_date in sorted(all_dates, reverse=True):
        record: dict[str, object] = {"date": observation_date.isoformat()}
        source_status: dict[str, str] = {}
        calculation_versions: dict[str, str] = {}
        for family_name, family_rows in families.items():
            family_row = family_rows.get(observation_date)
            if family_row is None:
                source_status[family_name] = "missing"
                continue
            record.update(family_row)
            if family_name == "finra":
                available_status = str(
                    family_row.get(
                        "finra_margin_source_status",
                        "retrospective_current_vintage",
                    )
                )
            elif family_name == "bdc":
                available_status = str(family_row.get("bdc_source_status", "ok"))
            elif family_name == "hy_oas":
                available_status = "history_bridge"
            else:
                available_status = "retrospective_current_vintage"
            source_status[family_name] = available_status
            version_key, version_value = CALCULATION_VERSIONS[family_name]
            calculation_versions[version_key] = version_value
        record["source_status_json"] = json.dumps(source_status, sort_keys=True)
        record["calculation_version_json"] = json.dumps(
            calculation_versions, sort_keys=True
        )
        record["updated_at_utc"] = updated_at_utc
        rows.append([record.get(column, "") for column in MACRO_DATA_COLUMNS])
    return rows


def validate_macro_rows(rows: list[list[object]]) -> None:
    if not rows or rows[0] != list(MACRO_DATA_COLUMNS):
        raise ValueError("MACRO_DATA header mismatch")
    width = len(MACRO_DATA_COLUMNS)
    status_index = MACRO_DATA_COLUMNS.index("source_status_json")
    version_index = MACRO_DATA_COLUMNS.index("calculation_version_json")
    column_indexes = {column: index for index, column in enumerate(MACRO_DATA_COLUMNS)}
    valid_statuses = {
        "ok",
        "missing",
        "stale",
        "kept_prior",
        "retrospective_current_vintage",
        "history_bridge",
        "partial",
        "shallow_accumulation",
    }
    expected_versions = {
        version_key: version_value
        for version_key, version_value in CALCULATION_VERSIONS.values()
    }
    dates: list[str] = []
    for row in rows[1:]:
        if len(row) != width:
            raise ValueError("MACRO_DATA row width mismatch")
        raw_date = str(row[0])
        datetime.strptime(raw_date, "%Y-%m-%d")
        dates.append(raw_date)
        try:
            statuses = json.loads(str(row[status_index] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid source status JSON") from exc
        if not isinstance(statuses, dict):
            raise ValueError("source status JSON must be an object")
        if set(statuses) != set(CALCULATION_VERSIONS):
            raise ValueError("source status JSON must contain every canonical family")
        unknown_statuses = {
            str(status) for status in statuses.values() if status not in valid_statuses
        }
        if unknown_statuses:
            raise ValueError(f"invalid source status values: {sorted(unknown_statuses)}")
        try:
            versions = json.loads(str(row[version_index] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid calculation version JSON") from exc
        if not isinstance(versions, dict):
            raise ValueError("calculation version JSON must be an object")
        for version_key, version_value in versions.items():
            if expected_versions.get(version_key) != version_value:
                raise ValueError(
                    f"invalid calculation version: {version_key}={version_value}"
                )
        for family, family_columns in MACRO_FAMILY_COLUMNS.items():
            populated = any(
                row[column_indexes[column]] not in (None, "")
                for column in family_columns
            )
            status = statuses[family]
            version_key = MACRO_FAMILY_VERSION_KEYS[family]
            if populated:
                if status not in MACRO_POPULATED_STATUSES[family]:
                    raise ValueError(
                        f"invalid status for populated {family}: {status}"
                    )
                if versions.get(version_key) != expected_versions[version_key]:
                    raise ValueError(
                        f"populated {family} requires calculation version {version_key}"
                    )
            else:
                if status != "missing":
                    raise ValueError(
                        f"empty {family} requires missing status, got {status}"
                    )
                if version_key in versions:
                    raise ValueError(
                        f"empty {family} may not carry calculation version {version_key}"
                    )
    if len(dates) != len(set(dates)):
        raise ValueError("MACRO_DATA duplicate dates")
    if dates != sorted(dates, reverse=True):
        raise ValueError("MACRO_DATA dates must be descending")


def validate_backfill_report(report: dict[str, object]) -> None:
    """Reject latest-only or truncated full builds before a destructive batch write."""
    failures: list[str] = []

    def as_int(value: object) -> int:
        return int(value) if isinstance(value, (str, int, float)) else 0

    row_count = as_int(report.get("row_count", 0))
    if row_count < 9000:
        failures.append(f"row_count={row_count}<9000")

    expected_first_on_or_before = {
        "finra": "1997-02-01",
        "nfci": "1971-01-31",
        "liquidity": "2003-01-01",
        "hy_oas": "1997-01-01",
        "bdc": "2026-05-23",
    }
    first_dates = report.get("first_date_by_metric_family", {})
    if not isinstance(first_dates, dict):
        failures.append("first_date_by_metric_family missing")
    else:
        for family, threshold in expected_first_on_or_before.items():
            actual = str(first_dates.get(family, ""))
            if not actual or actual > threshold:
                failures.append(f"{family}.first_date={actual or 'missing'}>{threshold}")

    minimum_counts = {
        "finra_margin_debt_usd": 300,
        "nfci_leverage": 2500,
        "fed_walcl": 1000,
        "fed_tga_wtregen": 1000,
        "fed_rrp_rpontsyd": 2500,
        "hy_oas": 6000,
        "bdc_regime_c_probability": 9,
    }
    counts = report.get("non_empty_count_by_column", {})
    if not isinstance(counts, dict):
        failures.append("non_empty_count_by_column missing")
    else:
        for column, minimum in minimum_counts.items():
            actual = as_int(counts.get(column, 0))
            if actual < minimum:
                failures.append(f"{column}.count={actual}<{minimum}")
    minimum_status_counts = {
        "finra:retrospective_current_vintage": 300,
        "nfci:retrospective_current_vintage": 2500,
        "liquidity:retrospective_current_vintage": 3000,
        "hy_oas:history_bridge": 6000,
        "bdc:ok": 9,
    }
    status_counts = report.get("source_status_counts", {})
    if not isinstance(status_counts, dict):
        failures.append("source_status_counts missing")
    else:
        for status_key, minimum in minimum_status_counts.items():
            actual = as_int(status_counts.get(status_key, 0))
            if actual < minimum:
                failures.append(
                    f"source_status_counts[{status_key}]={actual}<{minimum}"
                )
    if failures:
        raise ValueError("historical source-span gate failed: " + "; ".join(failures))


def build_backfill_report(rows: list[list[object]]) -> dict[str, object]:
    validate_macro_rows(rows)
    header = [str(value) for value in rows[0]]
    records = [dict(zip(header, row)) for row in rows[1:]]
    dates = [str(record["date"]) for record in records]
    family_columns = {
        "finra": ["finra_margin_debt_usd", "finra_rollover_warning"],
        "nfci": ["nfci_leverage", "nfci_leverage_warning"],
        "liquidity": ["fed_walcl", "liquidity_2of3_3m_warning"],
        "hy_oas": ["hy_oas", "hy_oas_warning"],
        "bdc": ["bdc_as_of_date", "bdc_regime_c_probability"],
    }
    first_by_family: dict[str, str] = {}
    last_by_family: dict[str, str] = {}
    for family, columns in family_columns.items():
        available_dates = sorted(
            str(record["date"])
            for record in records
            if any(record.get(column) not in (None, "") for column in columns)
        )
        if available_dates:
            first_by_family[family] = available_dates[0]
            last_by_family[family] = available_dates[-1]

    status_counts: Counter[str] = Counter()
    calculation_versions: dict[str, str] = {}
    for record in records:
        try:
            statuses = json.loads(str(record.get("source_status_json", "{}")))
            for family, status in statuses.items():
                status_counts[f"{family}:{status}"] += 1
        except json.JSONDecodeError as exc:
            raise ValueError("invalid source_status_json") from exc
        try:
            calculation_versions.update(
                json.loads(str(record.get("calculation_version_json", "{}")))
            )
        except json.JSONDecodeError as exc:
            raise ValueError("invalid calculation_version_json") from exc

    hash_columns = [column for column in header if column != "updated_at_utc"]
    hash_payload: list[list[object]] = [list(hash_columns)]
    for record in records:
        hash_payload.append([record.get(column, "") for column in hash_columns])
    payload = json.dumps(hash_payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "row_count": len(records),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "non_empty_count_by_column": {
            column: sum(record.get(column) not in (None, "") for record in records)
            for column in header
        },
        "first_date_by_metric_family": first_by_family,
        "last_date_by_metric_family": last_by_family,
        "source_status_counts": dict(sorted(status_counts.items())),
        "calculation_version": dict(sorted(calculation_versions.items())),
        "output_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }
