from pathlib import Path

from bankcap.diagnostics import run_first_pass_diagnostics
from bankcap.figures import write_mechanism_figures
from bankcap.h8 import build_h8_bank_group_panel
from bankcap.panel import build_analysis_panel
from bankcap.reporting import write_go_no_go_report, write_mechanism_memo
from bankcap.treasury_context import build_treasury_context

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def _make_panel(tmp_path):
    h8_path = tmp_path / "h8.csv"
    context_path = tmp_path / "context.csv"
    panel_path = tmp_path / "analysis.csv"
    build_h8_bank_group_panel(FIXTURES / "h8_synthetic_weekly.csv", h8_path, frequency="monthly")
    build_treasury_context(
        buycurve_path=FIXTURES / "buycurve_monthly_issuance.csv",
        tdcladder_path=FIXTURES / "tdcladder_monthly_ladder.csv",
        liqsub_path=FIXTURES / "liqsub_monthly.csv",
        output_path=context_path,
        project_config_path=ROOT / "config/project.yaml",
        episodes_config_path=ROOT / "config/episodes.yaml",
    )
    return build_analysis_panel(h8_path, context_path, panel_path), panel_path


def test_build_analysis_panel_and_diagnostics(tmp_path):
    panel, panel_path = _make_panel(tmp_path)
    assert len(panel) == 9
    assert panel["is_context_complete"].all()
    outputs = run_first_pass_diagnostics(panel_path, tmp_path / "diagnostics", event_window=1)
    for path in outputs.values():
        assert path.exists()
    assert outputs["bank_group_response_table"].read_text().startswith("bank_group")
    assert outputs["common_target_response_table"].exists()
    assert outputs["tga_complete_response_table"].exists()
    assert outputs["relative_bill_share_response_table"].exists()
    assert outputs["common_target_relative_bill_share_response_table"].exists()
    assert outputs["tga_complete_relative_bill_share_response_table"].exists()
    assert outputs["relative_bill_share_contrasts"].exists()
    assert outputs["sample_summary"].read_text().startswith("sample")


def test_write_go_no_go_report(tmp_path):
    _, panel_path = _make_panel(tmp_path)
    diag_dir = tmp_path / "diagnostics"
    run_first_pass_diagnostics(panel_path, diag_dir, event_window=1)
    report = write_go_no_go_report(
        panel_path=panel_path,
        diagnostics_dir=diag_dir,
        output_path=tmp_path / "go_no_go.md",
    )
    text = report.read_text()
    assert "Claim boundary" in text
    assert "NO-GO" in text or "GO" in text
    assert "Stability screen" in text
    assert "fixed bill/coupon support is insufficient" in text
    assert "Treat fixed bill/coupon contrasts as unsupported" in text


def test_write_mechanism_memo(tmp_path):
    _, panel_path = _make_panel(tmp_path)
    diag_dir = tmp_path / "diagnostics"
    run_first_pass_diagnostics(panel_path, diag_dir, event_window=1)
    memo = write_mechanism_memo(
        panel_path=panel_path,
        diagnostics_dir=diag_dir,
        output_path=tmp_path / "memo.md",
    )
    text = memo.read_text()
    assert "H.8 Mechanism-Screen Memo" in text
    assert "Relative high-bill and low-bill" in text
    assert "High-minus-low stability" in text
    assert "Interpretation boundary" in text
    assert "H.8 mechanism context only" in text


def test_write_mechanism_figures(tmp_path):
    _, panel_path = _make_panel(tmp_path)
    diag_dir = tmp_path / "diagnostics"
    run_first_pass_diagnostics(panel_path, diag_dir, event_window=1)
    outputs = write_mechanism_figures(
        panel_path=panel_path,
        diagnostics_dir=diag_dir,
        output_dir=tmp_path / "figures",
    )
    assert set(outputs) == {"ratio_trends", "relative_contrasts"}
    for path in outputs.values():
        text = path.read_text()
        assert text.startswith("<svg")
        assert "</svg>" in text
