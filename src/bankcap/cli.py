"""Command-line interface for the seeded bankcap project."""

from __future__ import annotations

import argparse
from pathlib import Path

from bankcap import __version__
from bankcap.config import validate_project_config
from bankcap.contracts import (
    import_contract_artifacts,
    load_source_contract,
    load_source_contracts,
    validate_contract,
)
from bankcap.diagnostics import run_first_pass_diagnostics
from bankcap.figures import write_mechanism_figures
from bankcap.h8 import build_h8_bank_group_panel
from bankcap.h8_ddp import build_target_group_h8_input, download_target_group_packages
from bankcap.panel import build_analysis_panel
from bankcap.reporting import write_go_no_go_report, write_mechanism_memo
from bankcap.treasury_context import build_treasury_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bankcap",
        description="H.8 bank-group capacity and Treasury financing diagnostics.",
    )
    parser.add_argument("--version", action="store_true", help="Print package version and exit.")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("validate-config", help="Validate project config, source contract paths, and schemas.")
    p.add_argument("--config", default="config/project.yaml")
    p.add_argument("--project-root", default=None)

    p = sub.add_parser("validate-sibling-sources", help="Validate source-contract artifacts.")
    p.add_argument("--contracts-dir", default="config/source_contracts")
    p.add_argument("--sibling", default=None, help="Validate one sibling project only.")
    p.add_argument("--project-root", default=".")
    p.add_argument("--source-root", default=None, help="Explicit source root. Use with --sibling.")
    p.add_argument("--imported", action="store_true", help="Check project-local imported paths instead of sibling roots.")
    p.add_argument("--required-only", action="store_true")
    p.add_argument("--strict-columns", action="store_true")

    p = sub.add_parser("copy-sibling-outputs", help="Copy/import sibling outputs into ignored local paths.")
    p.add_argument("--contracts-dir", default="config/source_contracts")
    p.add_argument("--sibling", required=True)
    p.add_argument("--source-root", required=True)
    p.add_argument("--project-root", default=".")
    p.add_argument("--required-only", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--manifest", default=None, help="Optional manifest CSV path.")

    p = sub.add_parser("build-h8-panel", help="Build the H.8 bank-group outcome panel.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="data/derived/h8_bank_group_panel.csv")
    p.add_argument("--frequency", choices=["monthly", "weekly"], default="monthly")
    p.add_argument("--monthly-method", choices=["last", "mean"], default="last")

    p = sub.add_parser("download-h8-target-groups", help="Download Fed H.8 target-group DDP packages.")
    p.add_argument("--output-dir", default="data/raw/h8_ddp")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--manifest", default="data/raw/h8_ddp/download_manifest.csv")

    p = sub.add_parser("build-h8-target-input", help="Normalize Fed H.8 target-group DDP packages.")
    p.add_argument("--input-dir", default="data/raw/h8_ddp")
    p.add_argument("--output", default="data/imported/h8_fed/target_group_h8_monthly_sa.csv")

    p = sub.add_parser("build-treasury-context", help="Build first-pass Treasury context from sibling outputs.")
    p.add_argument("--buycurve", default=None)
    p.add_argument("--tdcladder", default=None)
    p.add_argument("--liqsub", default=None)
    p.add_argument("--output", default="data/derived/treasury_context_panel.csv")
    p.add_argument("--project-config", default="config/project.yaml")
    p.add_argument("--episodes-config", default="config/episodes.yaml")

    p = sub.add_parser("build-analysis-panel", help="Merge H.8 outcomes and Treasury context.")
    p.add_argument("--h8", default="data/derived/h8_bank_group_panel.csv")
    p.add_argument("--context", default="data/derived/treasury_context_panel.csv")
    p.add_argument("--output", default="data/derived/bankcap_analysis_panel.csv")
    p.add_argument("--how", choices=["left", "inner"], default="left")

    p = sub.add_parser("run-diagnostics", help="Run first-pass descriptive diagnostics.")
    p.add_argument("--panel", default="data/derived/bankcap_analysis_panel.csv")
    p.add_argument("--output-dir", default="output/diagnostics")
    p.add_argument("--event-window", type=int, default=3)

    p = sub.add_parser("write-go-no-go-report", help="Write the H.8 go/no-go report.")
    p.add_argument("--panel", default="data/derived/bankcap_analysis_panel.csv")
    p.add_argument("--diagnostics-dir", default="output/diagnostics")
    p.add_argument("--output", default="output/reports/h8_go_no_go_report.md")

    p = sub.add_parser("write-mechanism-memo", help="Write a guarded H.8 mechanism-screen memo.")
    p.add_argument("--panel", default="data/derived/bankcap_analysis_panel.csv")
    p.add_argument("--diagnostics-dir", default="output/diagnostics")
    p.add_argument("--output", default="output/reports/h8_mechanism_screen_memo.md")

    p = sub.add_parser("write-mechanism-figures", help="Write H.8 mechanism-screen SVG figures.")
    p.add_argument("--panel", default="data/derived/bankcap_analysis_panel.csv")
    p.add_argument("--diagnostics-dir", default="output/diagnostics")
    p.add_argument("--output-dir", default="output/figures")

    return parser


def _print_issues(issues: list[str]) -> int:
    if not issues:
        print("OK")
        return 0
    for issue in issues:
        print(f"ISSUE: {issue}")
    return 1


def _cmd_validate_sibling_sources(args: argparse.Namespace) -> int:
    contracts = load_source_contracts(args.contracts_dir)
    if args.sibling:
        if args.sibling not in contracts:
            print(f"ISSUE: unknown sibling contract: {args.sibling}")
            return 1
        contracts = {args.sibling: contracts[args.sibling]}
    elif args.source_root:
        print("ISSUE: --source-root can only be used when --sibling selects one contract")
        return 1

    issues: list[str] = []
    for contract in contracts.values():
        issues.extend(
            validate_contract(
                contract,
                project_root=args.project_root,
                source_root=args.source_root,
                imported=args.imported,
                required_only=args.required_only,
                strict_columns=args.strict_columns,
            )
        )
    return _print_issues(issues)


def _cmd_copy_sibling_outputs(args: argparse.Namespace) -> int:
    contract_path = Path(args.contracts_dir) / f"{args.sibling}.yaml"
    contract = load_source_contract(contract_path)
    manifest = import_contract_artifacts(
        contract,
        project_root=args.project_root,
        source_root=args.source_root,
        required_only=args.required_only,
        overwrite=args.overwrite,
    )
    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest.to_csv(manifest_path, index=False)
        print(f"Wrote manifest: {manifest_path}")
    copied = int(manifest.get("copied", []).sum()) if not manifest.empty else 0
    print(f"Copied {copied} artifact(s) for {args.sibling}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "validate-config":
        return _print_issues(validate_project_config(args.config, project_root=args.project_root))
    if args.command == "validate-sibling-sources":
        return _cmd_validate_sibling_sources(args)
    if args.command == "copy-sibling-outputs":
        return _cmd_copy_sibling_outputs(args)
    if args.command == "build-h8-panel":
        panel = build_h8_bank_group_panel(
            args.input,
            args.output,
            frequency=args.frequency,
            monthly_method=args.monthly_method,
        )
        print(f"Wrote {len(panel)} rows: {args.output}")
        return 0
    if args.command == "download-h8-target-groups":
        manifest = download_target_group_packages(args.output_dir, overwrite=args.overwrite)
        if args.manifest:
            manifest_path = Path(args.manifest)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest.to_csv(manifest_path, index=False)
            print(f"Wrote manifest: {manifest_path}")
        downloaded = int(manifest["downloaded"].sum()) if not manifest.empty else 0
        print(f"Downloaded {downloaded} H.8 target-group package(s)")
        return 0
    if args.command == "build-h8-target-input":
        h8_input = build_target_group_h8_input(args.input_dir, args.output)
        print(f"Wrote {len(h8_input)} rows: {args.output}")
        return 0
    if args.command == "build-treasury-context":
        context = build_treasury_context(
            buycurve_path=args.buycurve,
            tdcladder_path=args.tdcladder,
            liqsub_path=args.liqsub,
            output_path=args.output,
            project_config_path=args.project_config,
            episodes_config_path=args.episodes_config,
        )
        print(f"Wrote {len(context)} rows: {args.output}")
        return 0
    if args.command == "build-analysis-panel":
        panel = build_analysis_panel(args.h8, args.context, args.output, how=args.how)
        print(f"Wrote {len(panel)} rows: {args.output}")
        return 0
    if args.command == "run-diagnostics":
        outputs = run_first_pass_diagnostics(args.panel, args.output_dir, event_window=args.event_window)
        print("Wrote diagnostics:")
        for name, path in outputs.items():
            print(f"- {name}: {path}")
        return 0
    if args.command == "write-go-no-go-report":
        report = write_go_no_go_report(
            panel_path=args.panel,
            diagnostics_dir=args.diagnostics_dir,
            output_path=args.output,
        )
        print(f"Wrote report: {report}")
        return 0
    if args.command == "write-mechanism-memo":
        memo = write_mechanism_memo(
            panel_path=args.panel,
            diagnostics_dir=args.diagnostics_dir,
            output_path=args.output,
        )
        print(f"Wrote memo: {memo}")
        return 0
    if args.command == "write-mechanism-figures":
        outputs = write_mechanism_figures(
            panel_path=args.panel,
            diagnostics_dir=args.diagnostics_dir,
            output_dir=args.output_dir,
        )
        print("Wrote figures:")
        for name, path in outputs.items():
            print(f"- {name}: {path}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
