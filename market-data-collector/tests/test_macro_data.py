from datetime import date
import json

import pytest

from src.services.macro_data import (
    build_bdc_family,
    build_finra_family,
    build_hy_oas_family,
    build_liquidity_family,
    build_macro_rows,
    build_backfill_report,
    validate_macro_rows,
    validate_backfill_report,
    build_nfci_family,
    _had_recent_blowoff_12m,
)


def test_nfci_family_uses_monthly_last_delta3_and_85th_percentile_positive_warning():
    rows = [
        (date(2025, month, 28), float(month - 1))
        for month in range(1, 11)
    ]

    family = build_nfci_family(rows)

    latest = family[date(2025, 10, 28)]
    assert latest["nfci_leverage"] == 9.0
    assert latest["nfci_leverage_delta_3m"] == 3.0
    assert latest["nfci_leverage_percentile"] == 100.0
    assert latest["nfci_leverage_warning"] is True


def test_nfci_family_preserves_weekly_raw_observations_between_month_ends():
    rows = [
        (date(2026, 1, 2), 0.1),
        (date(2026, 1, 9), 0.2),
        (date(2026, 1, 30), 0.3),
    ]

    family = build_nfci_family(rows)

    assert family[date(2026, 1, 2)] == {"nfci_leverage": 0.1}
    assert family[date(2026, 1, 9)] == {"nfci_leverage": 0.2}
    assert family[date(2026, 1, 30)]["nfci_leverage"] == 0.3


def test_liquidity_family_counts_walcl_contraction_tga_and_rrp_build_over_three_months():
    dates = [date(2025, month, 28) for month in range(1, 6)]
    walcl = [(day, 100.0 - index) for index, day in enumerate(dates)]
    tga = [(day, 10.0 + index) for index, day in enumerate(dates)]
    rrp = [(day, 5.0 - index) for index, day in enumerate(dates)]

    family = build_liquidity_family(walcl, tga, rrp)

    latest = family[date(2025, 5, 28)]
    assert latest["walcl_delta_3m"] == -3.0
    assert latest["wtregen_delta_3m"] == 3.0
    assert latest["rrp_delta_3m"] == -3.0
    assert latest["liquidity_tightening_component_count_3m"] == 2
    assert latest["liquidity_2of3_3m_warning"] is True


def test_liquidity_family_preserves_each_component_on_its_actual_source_dates():
    family = build_liquidity_family(
        [(date(2026, 1, 7), 100.0)],
        [(date(2026, 1, 8), 10.0)],
        [(date(2026, 1, 9), 5.0), (date(2026, 1, 12), 4.0)],
    )

    assert family[date(2026, 1, 7)] == {"fed_walcl": 100.0}
    assert family[date(2026, 1, 8)] == {"fed_tga_wtregen": 10.0}
    assert family[date(2026, 1, 9)] == {"fed_rrp_rpontsyd": 5.0}
    assert family[date(2026, 1, 12)]["fed_rrp_rpontsyd"] == 4.0


def test_hy_oas_family_uses_strict_60m_authority_and_trough_reversal_rule():
    oas = []
    spx = []
    for index in range(65):
        year = 2020 + index // 12
        month = index % 12 + 1
        day = date(year, month, 28)
        value = 3.0 if index == 60 else (3.4 if index == 64 else 5.0)
        oas.append((day, value, "archive" if index < 62 else "current_fred"))
        spx.append((day, 100.0 + index))

    family = build_hy_oas_family(oas, spx)

    latest = family[oas[-1][0]]
    assert latest["hy_oas"] == 3.4
    assert latest["hy_oas_source_regime"] == "current_fred"
    assert latest["hy_oas_trough_value"] == 3.0
    assert latest["hy_oas_months_since_trough"] == 4
    assert latest["hy_oas_widening_from_trough"] == 0.4
    assert latest["hy_oas_still_tight"] is True
    assert latest["hy_oas_sp500_near_high"] is True
    assert latest["hy_oas_warning"] is True
    assert latest["hy_oas_quality_status"] == "strict_60m_authority"


def test_hy_oas_family_preserves_daily_raw_observations_and_regime():
    family = build_hy_oas_family(
        [
            (date(2026, 7, 20), 2.69, "current_fred"),
            (date(2026, 7, 21), 2.70, "current_fred"),
        ],
        [(date(2026, 7, 21), 7509.2)],
    )

    assert family[date(2026, 7, 20)] == {
        "hy_oas": 2.69,
        "hy_oas_source_regime": "current_fred",
    }
    assert family[date(2026, 7, 21)]["hy_oas"] == 2.70


def test_hy_oas_rolling_authority_resets_after_calendar_gap():
    archive = [
        (date(2016 + (index // 12), index % 12 + 1, 28), 4.0 + index / 100, "archive")
        for index in range(60)
    ]
    post_gap = [(date(2023, 7, 31), 3.0, "current_fred")]

    family = build_hy_oas_family(
        archive + post_gap,
        [(date(2023, 7, 31), 100.0)],
    )

    post_gap_row = family[date(2023, 7, 31)]
    assert post_gap_row["hy_oas"] == 3.0
    assert "hy_oas_percentile_60m" not in post_gap_row
    assert "hy_oas_quality_status" not in post_gap_row


def test_hy_oas_uses_36_month_warmup_only_with_contiguous_post_gap_months():
    rows = [
        (
            date(2023 + ((6 + index) // 12), (6 + index) % 12 + 1, 28),
            3.0 + index / 100,
            "current_fred",
        )
        for index in range(36)
    ]
    spx = [(day, 100.0 + index) for index, (day, _, _) in enumerate(rows)]

    family = build_hy_oas_family(rows, spx)

    latest = family[rows[-1][0]]
    assert latest["hy_oas_quality_status"] == "dotcom_coverage_36m_warmup"


def test_finra_recent_blowoff_window_is_exactly_12_observations_including_current():
    assert _had_recent_blowoff_12m([100.0] + [0.0] * 12, 12) is False
    assert _had_recent_blowoff_12m([0.0, 100.0] + [0.0] * 11, 12) is True


def test_finra_family_places_rollover_on_one_month_lagged_signal_date():
    margin = []
    cpi = []
    spx = []
    for index in range(65):
        year = 2020 + index // 12
        month = index % 12 + 1
        day = date(year, month, 1)
        value = 100.0 + index
        if index == 55:
            value = 300.0
        elif index == 56:
            value = 310.0
        elif index == 57:
            value = 320.0
        elif index == 61:
            value = 300.0
        elif index == 64:
            value = 250.0
        margin.append((day, value))
        cpi.append((day, 100.0))
        spx.append((day, 100.0 + index))

    family = build_finra_family(margin, cpi, spx)

    latest = family[date(2025, 6, 1)]
    assert latest["finra_margin_date"] == "2025-05-01"
    assert latest["finra_margin_debt_usd"] == 250.0
    assert latest["finra_real_margin"] == 250.0
    assert latest["finra_current_growth_negative"] is True
    assert latest["finra_had_recent_blowoff"] is True
    assert latest["finra_sp500_near_high"] is True
    assert latest["finra_rollover_warning"] is True
    assert latest["finra_signal_authority"] == "short_warmup_sensitivity"


def test_finra_family_keeps_pre_warmup_raw_history_on_publication_lag_date():
    family = build_finra_family(
        [(date(1997, 1, 1), 103337.0)],
        [(date(1997, 1, 1), 100.0)],
        [(date(1997, 1, 31), 786.16)],
    )

    assert family[date(1997, 2, 1)] == {
        "finra_margin_date": "1997-01-01",
        "finra_margin_debt_usd": 103337.0,
        "finra_margin_source_status": "retrospective_current_vintage",
    }


def test_bdc_family_uses_export_availability_date_and_retains_payload_asof():
    family = build_bdc_family(
        [
            {
                "export_date": "2026-05-23",
                "bdc_as_of_date": "2026-05-16",
                "stage1_credit_quality": 101.0,
                "stage2_wrapper_repricing": 100.0,
                "stage3_funding_stress": 53.0,
                "stage4_credit_supply": 24.0,
                "stage5_macro_effects": 12.0,
                "stage6_feedback": 3.0,
                "regime_a_probability": 0.07,
                "regime_b_probability": 0.61,
                "regime_c_probability": 0.32,
                "status_code": "Orange",
                "source_status": "ok",
            }
        ]
    )

    assert date(2026, 5, 16) not in family
    assert family[date(2026, 5, 23)]["bdc_as_of_date"] == "2026-05-16"


def test_nfci_and_liquidity_do_not_bridge_missing_calendar_months():
    days = [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 4, 30),
        date(2026, 5, 31),
    ]
    nfci = build_nfci_family([(day, float(index)) for index, day in enumerate(days)])
    liquidity = build_liquidity_family(
        [(day, 100.0 - index) for index, day in enumerate(days)],
        [(day, 10.0 + index) for index, day in enumerate(days)],
        [(day, 5.0 + index) for index, day in enumerate(days)],
    )

    assert "nfci_leverage_delta_3m" not in nfci[days[-1]]
    assert "liquidity_2of3_3m_warning" not in liquidity[days[-1]]
    assert "walcl_delta_3m" not in liquidity[days[-1]]


def test_macro_rows_form_descending_union_and_leave_unavailable_cells_empty():
    finra = {
        date(2026, 5, 1): {
            "finra_margin_debt_usd": 100.0,
            "finra_margin_source_status": "retrospective_current_vintage",
        }
    }
    nfci = {date(2026, 5, 2): {"nfci_leverage": 0.2}}

    rows = build_macro_rows(
        finra=finra,
        nfci=nfci,
        liquidity={},
        hy_oas={},
        bdc={},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )

    header = rows[0]
    assert [row[0] for row in rows[1:]] == ["2026-05-02", "2026-05-01"]
    newest = dict(zip(header, rows[1]))
    oldest = dict(zip(header, rows[2]))
    assert newest["finra_margin_debt_usd"] == ""
    assert newest["nfci_leverage"] == 0.2
    assert oldest["finra_margin_debt_usd"] == 100.0
    assert oldest["nfci_leverage"] == ""
    newest_status = json.loads(str(newest["source_status_json"]))
    assert newest_status["nfci"] == "retrospective_current_vintage"

    validate_macro_rows(rows)
    report = build_backfill_report(rows)
    assert report["row_count"] == 2
    assert report["first_date"] == "2026-05-01"
    assert report["last_date"] == "2026-05-02"
    assert report["non_empty_count_by_column"]["finra_margin_debt_usd"] == 1
    assert report["first_date_by_metric_family"]["finra"] == "2026-05-01"
    assert report["last_date_by_metric_family"]["nfci"] == "2026-05-02"
    assert len(report["output_sha256"]) == 64


def test_backfill_hash_excludes_volatile_updated_at_timestamp():
    first = build_macro_rows(
        finra={},
        nfci={date(2026, 7, 10): {"nfci_leverage": 0.1}},
        liquidity={},
        hy_oas={},
        bdc={},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )
    second = build_macro_rows(
        finra={},
        nfci={date(2026, 7, 10): {"nfci_leverage": 0.1}},
        liquidity={},
        hy_oas={},
        bdc={},
        updated_at_utc="2026-07-22T11:00:00+00:00",
    )

    assert build_backfill_report(first)["output_sha256"] == build_backfill_report(second)["output_sha256"]


def test_macro_row_validator_rejects_unknown_status_and_calculation_version():
    rows = build_macro_rows(
        finra={},
        nfci={date(2026, 7, 10): {"nfci_leverage": 0.1}},
        liquidity={},
        hy_oas={},
        bdc={},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )
    status_index = rows[0].index("source_status_json")
    version_index = rows[0].index("calculation_version_json")

    invalid_status = [list(row) for row in rows]
    invalid_status[1][status_index] = json.dumps({"nfci": "totally_invalid"})
    with pytest.raises(ValueError, match="source status"):
        validate_macro_rows(invalid_status)

    invalid_version = [list(row) for row in rows]
    invalid_version[1][version_index] = json.dumps({"nfci_leverage": "invented_v99"})
    with pytest.raises(ValueError, match="calculation version"):
        validate_macro_rows(invalid_version)


def test_macro_row_validator_requires_family_metadata_coherence():
    nfci_rows = build_macro_rows(
        finra={},
        nfci={date(2026, 7, 10): {"nfci_leverage": 0.1}},
        liquidity={},
        hy_oas={},
        bdc={},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )
    status_index = nfci_rows[0].index("source_status_json")
    version_index = nfci_rows[0].index("calculation_version_json")

    missing_version = [list(row) for row in nfci_rows]
    missing_version[1][version_index] = "{}"
    with pytest.raises(ValueError, match="requires calculation version"):
        validate_macro_rows(missing_version)

    false_missing = [list(row) for row in nfci_rows]
    false_missing[1][status_index] = json.dumps(
        {family: "missing" for family in ("finra", "nfci", "liquidity", "hy_oas", "bdc")}
    )
    with pytest.raises(ValueError, match="invalid status for populated nfci"):
        validate_macro_rows(false_missing)

    hy_rows = build_macro_rows(
        finra={},
        nfci={},
        liquidity={},
        hy_oas={date(2026, 7, 10): {"hy_oas": 2.7}},
        bdc={},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )
    wrong_caveat = [list(row) for row in hy_rows]
    statuses = json.loads(str(wrong_caveat[1][status_index]))
    statuses["hy_oas"] = "retrospective_current_vintage"
    wrong_caveat[1][status_index] = json.dumps(statuses)
    with pytest.raises(ValueError, match="invalid status for populated hy_oas"):
        validate_macro_rows(wrong_caveat)


def test_backfill_report_validator_requires_retrospective_caveat_counts():
    report = {
        "row_count": 9000,
        "first_date_by_metric_family": {
            "finra": "1997-02-01",
            "nfci": "1971-01-08",
            "liquidity": "2002-12-18",
            "hy_oas": "1996-12-31",
            "bdc": "2026-05-23",
        },
        "non_empty_count_by_column": {
            "finra_margin_debt_usd": 300,
            "nfci_leverage": 2500,
            "fed_walcl": 1000,
            "fed_tga_wtregen": 1000,
            "fed_rrp_rpontsyd": 2500,
            "hy_oas": 6000,
            "bdc_regime_c_probability": 9,
        },
        "source_status_counts": {},
    }

    with pytest.raises(ValueError, match="source_status_counts"):
        validate_backfill_report(report)


def test_latest_only_backfill_report_fails_historical_source_span_gate():
    rows = build_macro_rows(
        finra={date(2026, 7, 1): {"finra_margin_debt_usd": 1.0}},
        nfci={date(2026, 7, 1): {"nfci_leverage": 0.1}},
        liquidity={date(2026, 7, 1): {"fed_walcl": 1.0, "fed_tga_wtregen": 1.0, "fed_rrp_rpontsyd": 1.0}},
        hy_oas={date(2026, 7, 1): {"hy_oas": 3.0}},
        bdc={date(2026, 7, 1): {"bdc_regime_c_probability": 0.2}},
        updated_at_utc="2026-07-22T10:00:00+00:00",
    )

    with pytest.raises(ValueError, match="historical source-span gate"):
        validate_backfill_report(build_backfill_report(rows))
