import json
from pathlib import Path

from bankcap.cli import main
from bankcap.diagnostics import run_first_pass_diagnostics
from bankcap.figures import write_mechanism_figures
from bankcap.h8 import build_h8_bank_group_panel
from bankcap.panel import build_analysis_panel
from bankcap.reporting import (
    write_go_no_go_report,
    write_mechanism_memo,
    write_mechanism_summary_json,
)
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
    assert outputs["relative_bill_share_cutoff_sensitivity"].exists()
    assert outputs["relative_bill_share_cutoff_sensitivity"].read_text().startswith("low_quantile")
    assert outputs["event_window_summary"].exists()
    assert outputs["event_window_contrasts"].exists()
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
    assert "Relative cutoff sensitivity" in text
    assert "Event-window screens" in text
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


def test_write_mechanism_summary_json(tmp_path):
    _, panel_path = _make_panel(tmp_path)
    diag_dir = tmp_path / "diagnostics"
    run_first_pass_diagnostics(panel_path, diag_dir, event_window=1)
    summary_path = write_mechanism_summary_json(
        panel_path=panel_path,
        diagnostics_dir=diag_dir,
        output_path=tmp_path / "summary.json",
    )
    summary = json.loads(summary_path.read_text())
    assert summary["package"] == "bankcap_h8_mechanism_screen"
    assert summary["bank_level_ingestion"]["status"] == "blocked"
    assert "not bank-level" in summary["claim_boundary"]


def test_cli_write_mechanism_package(tmp_path):
    _, panel_path = _make_panel(tmp_path)
    diag_dir = tmp_path / "diagnostics"
    report = tmp_path / "reports" / "go_no_go.md"
    memo = tmp_path / "reports" / "memo.md"
    summary = tmp_path / "reports" / "summary.json"
    manifest = tmp_path / "reports" / "manifest.csv"
    figures_dir = tmp_path / "figures"
    rc = main(
        [
            "write-mechanism-package",
            "--panel",
            str(panel_path),
            "--diagnostics-dir",
            str(diag_dir),
            "--report",
            str(report),
            "--memo",
            str(memo),
            "--summary",
            str(summary),
            "--manifest",
            str(manifest),
            "--figures-dir",
            str(figures_dir),
            "--event-window",
            "1",
        ]
    )
    assert rc == 0
    assert (diag_dir / "event_window_contrasts.csv").exists()
    assert (diag_dir / "relative_bill_share_cutoff_sensitivity.csv").exists()
    assert report.exists()
    assert memo.exists()
    assert summary.exists()
    assert manifest.exists()
    assert "claim_boundary" in manifest.read_text()
    assert "mechanism_summary" in manifest.read_text()
    assert (figures_dir / "h8_ratio_trends.svg").exists()
    assert (figures_dir / "relative_bill_share_contrasts.svg").exists()
    assert main(["validate-mechanism-package", "--manifest", str(manifest), "--project-root", str(tmp_path)]) == 0


def test_cli_validate_mechanism_package_rejects_missing_artifact(tmp_path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,name,path,claim_boundary\n"
        "input,analysis_panel,missing.csv,H.8 mechanism context only\n"
    )
    rc = main(["validate-mechanism-package", "--manifest", str(manifest), "--project-root", str(tmp_path)])
    assert rc == 1


def test_cli_validate_mechanism_package_rejects_report_without_boundary(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("This report has no required boundary language.\n")
    panel = tmp_path / "panel.csv"
    panel.write_text("period,bank_group\n")
    diagnostic = tmp_path / "diagnostic.csv"
    diagnostic.write_text("x\n1\n")
    figure = tmp_path / "figure.svg"
    figure.write_text("<svg></svg>")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,name,path,claim_boundary\n"
        "input,analysis_panel,panel.csv,H.8 mechanism context only\n"
        "diagnostic,sample_summary,diagnostic.csv,descriptive only\n"
        "report,go_no_go_report,report.md,not authorization for bank-level claims\n"
        "figure,ratio_trends,figure.svg,visual mechanism context only\n"
    )
    rc = main(["validate-mechanism-package", "--manifest", str(manifest), "--project-root", str(tmp_path)])
    assert rc == 1


def test_cli_validate_mechanism_package_rejects_empty_csv_and_bad_svg(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("## Claim boundary\nThis is not bank-level evidence.\n")
    panel = tmp_path / "panel.csv"
    panel.write_text("period,bank_group\n")
    diagnostic = tmp_path / "diagnostic.csv"
    diagnostic.write_text("x\n")
    figure = tmp_path / "figure.svg"
    figure.write_text("<svg>")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,name,path,claim_boundary\n"
        "input,analysis_panel,panel.csv,H.8 mechanism context only\n"
        "diagnostic,sample_summary,diagnostic.csv,descriptive only\n"
        "report,go_no_go_report,report.md,not authorization for bank-level claims\n"
        "figure,ratio_trends,figure.svg,visual mechanism context only\n"
    )
    rc = main(["validate-mechanism-package", "--manifest", str(manifest), "--project-root", str(tmp_path)])
    assert rc == 1


def test_cli_validate_mechanism_package_rejects_unblocked_summary(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("## Claim boundary\nThis is not bank-level evidence.\n")
    panel = tmp_path / "panel.csv"
    panel.write_text("period,bank_group\n2023-01,large_domestic_banks\n")
    diagnostic = tmp_path / "diagnostic.csv"
    diagnostic.write_text("x\n1\n")
    figure = tmp_path / "figure.svg"
    figure.write_text("<svg></svg>")
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"claim_boundary": "not bank-level", "bank_level_ingestion": {"status": "go"}}))
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,name,path,claim_boundary\n"
        "input,analysis_panel,panel.csv,H.8 mechanism context only\n"
        "diagnostic,sample_summary,diagnostic.csv,descriptive only\n"
        "report,go_no_go_report,report.md,not authorization for bank-level claims\n"
        "summary,mechanism_summary,summary.json,not bank-level\n"
        "figure,ratio_trends,figure.svg,visual mechanism context only\n"
    )
    rc = main(["validate-mechanism-package", "--manifest", str(manifest), "--project-root", str(tmp_path)])
    assert rc == 1


def test_cli_validate_mechanism_package_rejects_invalid_summary_json(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("## Claim boundary\nThis is not bank-level evidence.\n")
    panel = tmp_path / "panel.csv"
    panel.write_text("period,bank_group\n2023-01,large_domestic_banks\n")
    diagnostic = tmp_path / "diagnostic.csv"
    diagnostic.write_text("x\n1\n")
    figure = tmp_path / "figure.svg"
    figure.write_text("<svg></svg>")
    summary = tmp_path / "summary.json"
    summary.write_text('{"claim_boundary": "not bank-level",')
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,name,path,claim_boundary\n"
        "input,analysis_panel,panel.csv,H.8 mechanism context only\n"
        "diagnostic,sample_summary,diagnostic.csv,descriptive only\n"
        "report,go_no_go_report,report.md,not authorization for bank-level claims\n"
        "summary,mechanism_summary,summary.json,not bank-level\n"
        "figure,ratio_trends,figure.svg,visual mechanism context only\n"
    )
    rc = main(["validate-mechanism-package", "--manifest", str(manifest), "--project-root", str(tmp_path)])
    assert rc == 1
