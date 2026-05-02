from pathlib import Path

from bankcap.treasury_context import build_treasury_context

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_build_treasury_context_from_sibling_fixtures(tmp_path):
    output = tmp_path / "context.csv"
    context = build_treasury_context(
        buycurve_path=FIXTURES / "buycurve_monthly_issuance.csv",
        tdcladder_path=FIXTURES / "tdcladder_monthly_ladder.csv",
        liqsub_path=FIXTURES / "liqsub_monthly.csv",
        output_path=output,
        project_config_path=ROOT / "config/project.yaml",
        episodes_config_path=ROOT / "config/episodes.yaml",
    )
    assert output.exists()
    assert len(context) == 3
    assert bool(context.loc[context["period"] == "2023-01", "bill_heavy_month"].iloc[0]) is True
    assert bool(context.loc[context["period"] == "2023-02", "coupon_heavy_month"].iloc[0]) is True
    assert bool(context.loc[context["period"] == "2023-01", "high_bill_share_month"].iloc[0]) is True
    assert bool(context.loc[context["period"] == "2023-02", "low_bill_share_month"].iloc[0]) is True
    assert context.loc[context["period"] == "2023-02", "bill_share_bucket"].iloc[0] == "low_bill_share"
    assert bool(context.loc[context["period"] == "2023-03", "banking_stress_2023_window"].iloc[0]) is True
    assert bool(context.loc[context["period"] == "2023-03", "large_tga_rebuild_window"].iloc[0]) is True
    assert context.loc[context["period"] == "2023-03", "qt_qe_regime"].iloc[0] == "QT"


def test_build_treasury_context_from_real_sibling_shapes(tmp_path):
    buycurve = tmp_path / "buycurve_long.csv"
    buycurve.write_text(
        "month,security_type,accepted_amount_sum,weighted_maturity_years\n"
        "2023-01-01,Bill,75,0.25\n"
        "2023-01-01,Note,25,5\n"
        "2023-02-01,Bond,100,20\n"
    )
    tdcladder = tmp_path / "tdcladder.csv"
    tdcladder.write_text(
        "month,weight_family,supply_basis,raw_bill_share,raw_weighted_maturity_years,liquid_treasury_supply\n"
        "2023-01-01,fixed_baseline,issuance_flow,0.75,1,500\n"
        "2023-01-01,other,issuance_flow,0.10,9,100\n"
        "2023-02-01,fixed_baseline,issuance_flow,0.00,20,600\n"
    )
    liqsub = tmp_path / "liqsub.csv"
    liqsub.write_text("month,tga,iorb_rate,qe_qt_regime\n2023-01-01,100,4.5,QT\n2023-02-01,250,4.75,QT\n")
    context = build_treasury_context(
        buycurve_path=buycurve,
        tdcladder_path=tdcladder,
        liqsub_path=liqsub,
        output_path=tmp_path / "context.csv",
        project_config_path=ROOT / "config/project.yaml",
        episodes_config_path=ROOT / "config/episodes.yaml",
    )
    jan = context.loc[context["period"] == "2023-01"].iloc[0]
    feb = context.loc[context["period"] == "2023-02"].iloc[0]
    assert jan["bill_share"] == 0.75
    assert jan["gross_issuance_usd"] == 100
    assert feb["tga_change_usd_millions"] == 150
    assert bool(feb["high_rate_regime"]) is True
