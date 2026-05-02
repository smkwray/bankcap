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
    assert bool(context.loc[context["period"] == "2023-03", "banking_stress_2023_window"].iloc[0]) is True
    assert bool(context.loc[context["period"] == "2023-03", "large_tga_rebuild_window"].iloc[0]) is True
    assert context.loc[context["period"] == "2023-03", "qt_qe_regime"].iloc[0] == "QT"
