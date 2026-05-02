from pathlib import Path

from bankcap.cli import main
from bankcap.contracts import import_contract_artifacts, load_source_contract, validate_contract

ROOT = Path(__file__).resolve().parents[1]


def test_contract_validation_and_import(tmp_path):
    source_root = tmp_path / "buycurve"
    source_file = source_root / "data/clean/monthly_issuance_maturity_panel.csv"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("month,bill_share,gross_issuance_usd\n2023-01,0.7,100\n")

    contract = load_source_contract(ROOT / "config/source_contracts/buycurve.yaml")
    issues = validate_contract(
        contract,
        project_root=tmp_path / "project",
        source_root=source_root,
        required_only=True,
        strict_columns=True,
    )
    assert issues == []
    manifest = import_contract_artifacts(
        contract,
        project_root=tmp_path / "project",
        source_root=source_root,
        required_only=True,
    )
    assert manifest["copied"].all()
    assert (tmp_path / "project/data/imported/buycurve/monthly_issuance_maturity_panel.csv").exists()


def test_cli_validate_config():
    assert main(["validate-config", "--config", str(ROOT / "config/project.yaml")]) == 0


def test_cli_build_h8(tmp_path):
    out = tmp_path / "h8.csv"
    rc = main(
        [
            "build-h8-panel",
            "--input",
            str(ROOT / "tests/fixtures/h8_synthetic_weekly.csv"),
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    assert out.exists()
