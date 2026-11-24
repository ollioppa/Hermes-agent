import json

import pandas as pd
from unittest.mock import patch

from src.scripts import market_briefing_snapshot as snapshot_module
from src.scripts.market_briefing_snapshot import (
    build_macro_snapshot,
    normalize_macro_types,
    to_jsonable,
)


def test_macro_snapshot_resolves_sparse_family_from_latest_non_empty_row_with_source_date():
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-07-21"),
                "finra_margin_debt_usd": "",
                "finra_margin_date": "",
                "finra_rollover_warning": "",
                "source_status_json": json.dumps({"finra": "missing"}),
            },
            {
                "date": pd.Timestamp("2026-07-01"),
                "finra_margin_debt_usd": 1502072.0,
                "finra_margin_date": "2026-06-01",
                "finra_rollover_warning": False,
                "source_status_json": json.dumps(
                    {"finra": "retrospective_current_vintage"}
                ),
            },
        ]
    )

    snapshot = build_macro_snapshot(frame)

    assert snapshot["finra"]["current_value"] == 1502072.0
    assert snapshot["finra"]["sheet_date"] == "2026-07-01"
    assert snapshot["finra"]["effective_date"] == "2026-06-01"
    assert snapshot["finra"]["source_status"] == "retrospective_current_vintage"


def test_macro_snapshot_resolves_each_metric_latest_valid_not_one_family_row():
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-07-01"),
                "finra_margin_debt_usd": "",
                "finra_rollover_warning": True,
                "finra_signal_authority": "short_warmup_sensitivity",
            },
            {
                "date": pd.Timestamp("2026-06-01"),
                "finra_margin_debt_usd": 1415557.0,
                "finra_margin_date": "2026-05-01",
                "finra_rollover_warning": "",
            },
            {
                "date": pd.Timestamp("2026-05-01"),
                "finra_margin_debt_usd": "",
                "finra_real_margin_growth_3m_annualized": 1.25,
                "finra_rollover_warning": "",
            },
        ]
    )

    snapshot = build_macro_snapshot(frame)

    assert snapshot["finra"]["current_value"] == 1415557.0
    assert snapshot["finra"]["warning"] is True
    assert snapshot["finra"]["warning_sheet_date"] == "2026-07-01"
    assert snapshot["finra"]["metrics"]["finra_signal_authority"] == {
        "value": "short_warmup_sensitivity",
        "sheet_date": "2026-07-01",
        "effective_date": "2026-07-01",
        "source_status": None,
        "calculation_version": None,
    }
    assert snapshot["finra"]["metrics"]["finra_real_margin_growth_3m_annualized"]["value"] == 1.25
    assert snapshot["finra"]["metrics"]["finra_real_margin_growth_3m_annualized"]["sheet_date"] == "2026-05-01"


def test_macro_snapshot_does_not_treat_newest_blank_row_as_missing_family():
    frame = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-07-21"), "bdc_regime_c_probability": ""},
            {
                "date": pd.Timestamp("2026-07-07"),
                "bdc_regime_c_probability": 0.2,
                "bdc_as_of_date": "2026-07-05",
                "bdc_status_code": "Rot",
                "bdc_source_status": "ok",
            },
        ]
    )

    snapshot = build_macro_snapshot(frame)

    assert snapshot["bdc"]["current_value"] == 0.2
    assert snapshot["bdc"]["effective_date"] == "2026-07-05"


def test_macro_snapshot_includes_cross_family_metrics_with_row_local_metadata():
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-07-20"),
                "finra_margin_debt_usd": 100.0,
                "finra_margin_date": "2026-06-01",
                "cpi_index": 320.0,
                "sp500_close": 6200.0,
                "sp500_12m_high": 6300.0,
                "fed_walcl": 6_000_000.0,
                "walcl_delta_3m": -100_000.0,
                "wtregen_delta_3m": 20_000.0,
                "rrp_delta_3m": 30_000.0,
                "liquidity_tightening_component_count_3m": 3,
                "source_status_json": json.dumps(
                    {
                        "finra": "retrospective_current_vintage",
                        "liquidity": "retrospective_current_vintage",
                    }
                ),
                "calculation_version_json": json.dumps(
                    {
                        "finra_margin": "finra_blowoff_rollover_v6a",
                        "net_fed_liquidity": "component_agreement_2of3_3m_v1",
                    }
                ),
            }
        ]
    )

    snapshot = build_macro_snapshot(frame)

    for metric in ("cpi_index", "sp500_close", "sp500_12m_high"):
        assert metric in snapshot["finra"]["metrics"]
        assert snapshot["finra"]["metrics"][metric]["source_status"] == "retrospective_current_vintage"
        assert snapshot["finra"]["metrics"][metric]["calculation_version"] == "finra_blowoff_rollover_v6a"
    assert snapshot["finra"]["metrics"]["cpi_index"]["effective_date"] == "2026-06-01"
    assert snapshot["finra"]["metrics"]["sp500_close"]["effective_date"] == "2026-07-20"
    for metric in ("walcl_delta_3m", "wtregen_delta_3m", "rrp_delta_3m"):
        assert metric in snapshot["liquidity"]["metrics"]
        assert snapshot["liquidity"]["metrics"][metric]["calculation_version"] == "component_agreement_2of3_3m_v1"


def test_macro_type_normalization_preserves_sparse_booleans_and_json_scalars():
    frame = pd.DataFrame(
        {
            "date": ["2026-07-20", "2026-07-19"],
            "hy_oas_warning": [False, pd.NA],
            "hy_oas_months_since_trough": [3, ""],
        }
    )

    normalized = normalize_macro_types(frame)
    snapshot = build_macro_snapshot(normalized.assign(hy_oas=[2.7, ""]))
    rendered = json.dumps(to_jsonable(snapshot))

    assert snapshot["hy_oas"]["metrics"]["hy_oas_warning"]["value"] is False
    assert '"value": false' in rendered


def test_consumer_gate_is_independent_from_daily_mutation_gate(capsys):
    db = pd.DataFrame(
        [{"date": pd.Timestamp("2026-07-21"), "source_status_json": "{}"}]
    )
    market = pd.DataFrame([{"date": pd.Timestamp("2026-07-21")}])
    with (
        patch.object(snapshot_module, "MACRO_DATA_CONSUMER_ENABLED", False),
        patch.object(
            snapshot_module,
            "sheet_to_df",
            side_effect=lambda name: {"DB": db, "MARKET_DATA": market}[name],
        ) as reader,
        patch.object(snapshot_module, "build_thermometer_snapshot", return_value={}),
    ):
        snapshot_module.main()

    payload = json.loads(capsys.readouterr().out)
    assert [item.args[0] for item in reader.call_args_list] == ["DB", "MARKET_DATA"]
    assert payload["macro"] == {}


def test_main_reads_macro_data_sheet_and_emits_macro_contract(capsys):
    db = pd.DataFrame(
        [{"date": pd.Timestamp("2026-07-21"), "source_status_json": "{}"}]
    )
    market = pd.DataFrame([{"date": pd.Timestamp("2026-07-21")}])
    macro = pd.DataFrame(
        [{"date": pd.Timestamp("2026-07-20"), "hy_oas": 2.69}]
    )

    with (
        patch.object(snapshot_module, "MACRO_DATA_CONSUMER_ENABLED", True),
        patch.object(
            snapshot_module,
            "sheet_to_df",
            side_effect=lambda name: {"DB": db, "MARKET_DATA": market, "MACRO_DATA": macro}[name],
        ) as reader,
        patch.object(snapshot_module, "build_thermometer_snapshot", return_value={}),
    ):
        snapshot_module.main()

    payload = json.loads(capsys.readouterr().out)
    assert reader.call_args_list[-1].args == ("MACRO_DATA",)
    assert payload["macro"]["hy_oas"]["current_value"] == 2.69
