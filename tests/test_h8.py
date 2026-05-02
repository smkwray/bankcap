from pathlib import Path

import pandas as pd

from bankcap.h8 import build_h8_bank_group_panel
from bankcap.h8_ddp import build_target_group_h8_input, normalize_h8_ddp_package, target_packages

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


def test_normalize_h8_ddp_package(tmp_path):
    source = tmp_path / "large.csv"
    source.write_text(
        '"Series Description","Treasury and agency securities","Loans","Cash assets","Deposits"\n'
        '"Unit:","Currency","Currency","Currency","Currency"\n'
        '"Multiplier:","1000000","1000000","1000000","1000000"\n'
        '"Currency:","USD","USD","USD","USD"\n'
        '"Unique Identifier:","H8/H8/B1003NLGAM","H8/H8/B1020NLGAM","H8/H8/B1048NLGAM","H8/H8/B1058NLGAM"\n'
        '"Time Period","B1003NLGAM","B1020NLGAM","B1048NLGAM","B1058NLGAM"\n'
        "2023-01,250,700,100,1000\n"
    )
    out = normalize_h8_ddp_package(source, "large_domestic_banks")
    row = out.iloc[0]
    assert row["date"].strftime("%Y-%m-%d") == "2023-01-01"
    assert row["bank_group"] == "large_domestic_banks"
    assert row["securities_usd_millions"] == 250
    assert row["loans_usd_millions"] == 700
    assert row["cash_assets_usd_millions"] == 100
    assert row["deposits_usd_millions"] == 1000


def test_build_target_group_h8_input(tmp_path):
    for package in target_packages():
        (tmp_path / package.filename).write_text(
            '"Series Description","Treasury and agency securities","Loans","Cash assets","Deposits"\n'
            '"Unit:","Currency","Currency","Currency","Currency"\n'
            '"Multiplier:","1000000","1000000","1000000","1000000"\n'
            '"Currency:","USD","USD","USD","USD"\n'
            '"Unique Identifier:","H8/H8/B1003TEST","H8/H8/B1020TEST","H8/H8/B1048TEST","H8/H8/B1058TEST"\n'
            '"Time Period","B1003TEST","B1020TEST","B1048TEST","B1058TEST"\n'
            "2023-01,250,700,100,1000\n"
        )
    out = build_target_group_h8_input(tmp_path)
    assert len(out) == 3
    assert set(out["bank_group"]) == {
        "large_domestic_banks",
        "small_domestic_banks",
        "foreign_related_institutions",
    }


def test_build_target_group_h8_input_drops_incomplete_rows(tmp_path):
    for package in target_packages():
        value = "" if package.bank_group == "small_domestic_banks" else "250"
        (tmp_path / package.filename).write_text(
            '"Series Description","Treasury and agency securities","Loans","Cash assets","Deposits"\n'
            '"Unit:","Currency","Currency","Currency","Currency"\n'
            '"Multiplier:","1000000","1000000","1000000","1000000"\n'
            '"Currency:","USD","USD","USD","USD"\n'
            '"Unique Identifier:","H8/H8/B1003TEST","H8/H8/B1020TEST","H8/H8/B1048TEST","H8/H8/B1058TEST"\n'
            '"Time Period","B1003TEST","B1020TEST","B1048TEST","B1058TEST"\n'
            f"2023-01,{value},700,100,1000\n"
        )
    out = build_target_group_h8_input(tmp_path)
    assert len(out) == 2
    assert "small_domestic_banks" not in set(out["bank_group"])
