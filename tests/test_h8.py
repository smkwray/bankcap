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
