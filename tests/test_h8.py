from pathlib import Path

import pandas as pd

from bankcap.h8 import build_h8_bank_group_panel

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_build_h8_monthly_panel(tmp_path):
    output = tmp_path / "h8.csv"
    panel = build_h8_bank_group_panel(
        FIXTURES / "h8_synthetic_weekly.csv", output, frequency="monthly", monthly_method="last"
    )
    assert output.exists()
    assert len(panel) == 9
    assert set(panel["bank_group"]) == {
        "large_domestic_banks",
        "small_domestic_banks",
        "foreign_related_institutions",
    }
    jan_large = panel[(panel["period"] == "2023-01") & (panel["bank_group"] == "large_domestic_banks")].iloc[0]
    assert jan_large["securities_usd_millions"] == 1020
    assert jan_large["securities_deposits_ratio"] == 1020 / 5020
    mar_large = panel[(panel["period"] == "2023-03") & (panel["bank_group"] == "large_domestic_banks")].iloc[0]
    assert mar_large["d_securities_usd_millions"] == 40


def test_build_h8_weekly_panel():
    panel = build_h8_bank_group_panel(FIXTURES / "h8_synthetic_weekly.csv", frequency="weekly")
    assert len(panel) == 18
    assert panel["period"].str.len().eq(10).all()
    assert pd.to_numeric(panel["cash_deposits_ratio"]).notna().all()


def test_build_h8_from_liqsub_aggregate_shape(tmp_path):
    source = tmp_path / "liqsub_h8.csv"
    source.write_text(
        "month,deposits,cash_assets,bank_treasury_agency_securities,total_bank_credit\n"
        "2023-01-01,1000,100,250,700\n"
        "2023-02-01,1100,90,260,720\n"
    )
    panel = build_h8_bank_group_panel(source, frequency="monthly")
    assert set(panel["bank_group"]) == {"all_commercial_banks"}
    assert panel.loc[panel["period"] == "2023-01", "loans_usd_millions"].iloc[0] == 450
    assert panel.loc[panel["period"] == "2023-02", "d_cash_assets_usd_millions"].iloc[0] == -10


def test_build_h8_from_buycurve_h8_context_shape(tmp_path):
    source = tmp_path / "buycurve_h8_context.csv"
    source.write_text(
        "month,bank_group,bank_credit_month_latest,securities_in_bank_credit_month_latest,"
        "treasury_agency_securities_month_latest,cash_assets_month_latest,deposits_month_latest\n"
        "2023-01-01,domestically_chartered_banks,900,300,225,120,1000\n"
    )
    panel = build_h8_bank_group_panel(source, frequency="monthly")
    row = panel.iloc[0]
    assert row["bank_group"] == "domestically_chartered_banks"
    assert row["loans_usd_millions"] == 600
    assert row["securities_usd_millions"] == 225
