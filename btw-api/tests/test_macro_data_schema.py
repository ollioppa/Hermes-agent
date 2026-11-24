from src.config.settings import MACRO_DATA_COLUMNS, MACRO_DATA_COLUMN_TYPES


EXPECTED_MACRO_DATA_COLUMNS = [
    "date",
    "finra_margin_date",
    "finra_margin_debt_usd",
    "finra_margin_source_status",
    "cpi_index",
    "sp500_close",
    "sp500_12m_high",
    "finra_real_margin",
    "finra_real_margin_growth_3m_annualized",
    "finra_growth_percentile_60m",
    "finra_had_recent_blowoff",
    "finra_current_growth_negative",
    "finra_sp500_near_high",
    "finra_rollover_warning",
    "finra_signal_authority",
    "nfci_leverage",
    "nfci_leverage_delta_3m",
    "nfci_leverage_percentile",
    "nfci_leverage_warning",
    "fed_walcl",
    "fed_tga_wtregen",
    "fed_rrp_rpontsyd",
    "walcl_delta_3m",
    "wtregen_delta_3m",
    "rrp_delta_3m",
    "liquidity_tightening_component_count_3m",
    "liquidity_2of3_3m_warning",
    "hy_oas",
    "hy_oas_source_regime",
    "hy_oas_percentile_60m",
    "hy_oas_trough_value",
    "hy_oas_months_since_trough",
    "hy_oas_widening_from_trough",
    "hy_oas_still_tight",
    "hy_oas_sp500_near_high",
    "hy_oas_warning",
    "hy_oas_quality_status",
    "bdc_as_of_date",
    "bdc_stage1_credit_quality",
    "bdc_stage2_wrapper_repricing",
    "bdc_stage3_funding_stress",
    "bdc_stage4_credit_supply",
    "bdc_stage5_macro_effects",
    "bdc_stage6_feedback",
    "bdc_regime_a_probability",
    "bdc_regime_b_probability",
    "bdc_regime_c_probability",
    "bdc_status_code",
    "bdc_source_status",
    "source_status_json",
    "calculation_version_json",
    "updated_at_utc",
]


def test_macro_data_header_is_exactly_the_reviewed_wide_schema():
    assert MACRO_DATA_COLUMNS == EXPECTED_MACRO_DATA_COLUMNS


def test_macro_data_schema_stays_under_review_limit_and_contains_no_prose_fields():
    assert len(MACRO_DATA_COLUMNS) == 52
    assert len(MACRO_DATA_COLUMNS) <= 64
    assert not {"reader_label", "interpretation", "watch_next"} & set(MACRO_DATA_COLUMNS)


def test_every_macro_column_has_an_explicit_sheet_type():
    assert list(MACRO_DATA_COLUMN_TYPES) == MACRO_DATA_COLUMNS
    assert MACRO_DATA_COLUMN_TYPES["date"] == "date"
    assert MACRO_DATA_COLUMN_TYPES["source_status_json"] == "json"
    assert MACRO_DATA_COLUMN_TYPES["finra_rollover_warning"] == "boolean"
    assert MACRO_DATA_COLUMN_TYPES["bdc_stage1_credit_quality"] == "integer"
    assert MACRO_DATA_COLUMN_TYPES["hy_oas"] == "number"
