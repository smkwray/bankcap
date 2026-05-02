"""Go/no-go reporting for the H.8 bank-group screen."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bankcap.diagnostics import target_common_panel, tga_complete_target_panel
from bankcap.io import ensure_parent, read_csv

CLAIM_BOUNDARY_TEXT = """\
## Claim boundary

This report is a mechanism screen, not bank-level identification. H.8 bank-group data cannot support
claims about individual-bank heterogeneity, merger-adjusted bank behavior, bank-level duration
exposure, or causal absorption. H.8 securities should be labeled as an aggregate that may combine
Treasury and agency securities unless a source-specific mapping proves otherwise.
"""

TARGET_H8_GROUPS = {
    "large_domestic_banks",
    "small_domestic_banks",
    "foreign_related_institutions",
}


def _target_common_panel(panel: pd.DataFrame) -> pd.DataFrame:
    return target_common_panel(panel)


def _diagnostic_signal(panel: pd.DataFrame) -> tuple[str, list[str]]:
    periods = panel["period"].nunique() if "period" in panel.columns else 0
    groups = panel["bank_group"].nunique() if "bank_group" in panel.columns else 0
    observed_groups = set(panel["bank_group"].dropna().astype(str)) if "bank_group" in panel.columns else set()
    target_groups = len(observed_groups.intersection(TARGET_H8_GROUPS))
    target_common = _target_common_panel(panel)
    target_common_periods = target_common["period"].nunique() if len(target_common) else 0
    context_complete = (
        float(target_common.get("is_context_complete", pd.Series(False, index=target_common.index)).mean())
        if len(target_common)
        else 0.0
    )
    bill_variation_frame = target_common if len(target_common) else panel
    bill_variation = (
        bill_variation_frame.get(
            "bill_heavy_month", pd.Series(False, index=bill_variation_frame.index)
        ).nunique()
        > 1
        or bill_variation_frame.get(
            "coupon_heavy_month", pd.Series(False, index=bill_variation_frame.index)
        ).nunique()
        > 1
    )
    coupon_rows = int(
        bill_variation_frame.get(
            "coupon_heavy_month", pd.Series(False, index=bill_variation_frame.index)
        )
        .fillna(False)
        .astype(bool)
        .sum()
    )
    high_bill_rows = int(
        bill_variation_frame.get(
            "high_bill_share_month", pd.Series(False, index=bill_variation_frame.index)
        )
        .fillna(False)
        .astype(bool)
        .sum()
    )
    low_bill_rows = int(
        bill_variation_frame.get(
            "low_bill_share_month", pd.Series(False, index=bill_variation_frame.index)
        )
        .fillna(False)
        .astype(bool)
        .sum()
    )

    reasons = [
        f"sample periods: {periods}",
        f"bank groups observed: {groups}",
        f"target H.8 groups observed: {target_groups} of {len(TARGET_H8_GROUPS)}",
        f"common target-group periods: {target_common_periods}",
        f"common-sample context-complete row share: {context_complete:.2f}",
        f"fixed-threshold bill/coupon variation present: {bill_variation}",
        f"fixed-threshold coupon-heavy rows: {coupon_rows}",
        f"relative high-bill rows: {high_bill_rows}",
        f"relative low-bill rows: {low_bill_rows}",
    ]
    if target_groups == 0:
        reasons.append("current H.8 reuse is aggregate-only; large/small/foreign split is still missing")
        return "NO-GO for heavy bank-level ingestion until target H.8 group coverage is available", reasons
    if target_common_periods >= 24 and target_groups >= 3 and context_complete >= 0.75 and bill_variation:
        return "PROVISIONAL GO for a scoped bank-level design memo", reasons
    if target_common_periods >= 12 and target_groups >= 2 and bill_variation:
        return "PARTIAL GO: improve coverage before Call Report or FR Y-9C ingestion", reasons
    return "NO-GO for heavy bank-level ingestion until H.8 coverage/context improves", reasons


def write_go_no_go_report(
    *,
    panel_path: str | Path,
    output_path: str | Path,
    diagnostics_dir: str | Path | None = None,
) -> Path:
    """Write a concise markdown go/no-go report for review."""

    panel = read_csv(panel_path)
    recommendation, reasons = _diagnostic_signal(panel)
    out = ensure_parent(output_path)

    diagnostics_note = ""
    if diagnostics_dir is not None:
        diag = Path(diagnostics_dir)
        available = sorted(path.name for path in diag.glob("*.csv")) if diag.exists() else []
        diagnostics_note = "\n## Diagnostic tables reviewed\n\n" + "\n".join(
            f"- `{name}`" for name in available
        )
        if not available:
            diagnostics_note += "- No diagnostic tables found.\n"

    group_rows = []
    for group, gdf in panel.groupby("bank_group"):
        group_rows.append(
            f"- `{group}`: {len(gdf)} rows, {gdf['period'].min()} to {gdf['period'].max()}"
        )

    report = f"""# bankcap H.8 Go/No-Go Report

## Recommendation

**{recommendation}.**

## Gate checks

{chr(10).join(f"- {reason}" for reason in reasons)}

## Bank-group coverage

{chr(10).join(group_rows) if group_rows else "- No bank-group rows found."}

## Interpretation

A GO result means only that the low-cost H.8 mechanism screen has enough variation and coverage to
justify drafting a bank-level design memo. It does not mean that bank-level data engineering should
begin without an explicit MDRM-code map, identifier strategy, merger/survivorship plan, and
pre-trend specification.
{diagnostics_note}
{CLAIM_BOUNDARY_TEXT}
## Next implementation branch

1. Inspect bill-heavy versus coupon-heavy response tables by bank group.
2. Check whether securities/deposits, cash/deposits, and loans/deposits move differently across
   large domestic, small domestic, and foreign-related groups.
3. Draft a Call Report / FR Y-9C data-cost memo only if the screen shows stable, interpretable
   variation that is not solely a calendar-regime artifact.
"""
    out.write_text(report, encoding="utf-8")
    return out


def _fmt_number(value: object, digits: int = 2) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "NA"
    if pd.isna(numeric):
        return "NA"
    return f"{numeric:.{digits}f}"


def _response_lines(response: pd.DataFrame, *, max_rows: int | None = None) -> list[str]:
    if response.empty:
        return ["- No response table is available."]
    lines = []
    bucket_col = "treasury_context_bucket"
    if bucket_col not in response.columns and "relative_bill_share_bucket" in response.columns:
        bucket_col = "relative_bill_share_bucket"
    ordered = response.sort_values(["bank_group", bucket_col])
    if max_rows is not None:
        ordered = ordered.head(max_rows)
    for _, row in ordered.iterrows():
        lines.append(
            "- "
            f"`{row['bank_group']}` / `{row[bucket_col]}`: "
            f"n={int(row['n_rows'])}, "
            f"d_securities={_fmt_number(row.get('d_securities_usd_millions'), 1)}, "
            f"d_deposits={_fmt_number(row.get('d_deposits_usd_millions'), 1)}, "
            f"d_loans={_fmt_number(row.get('d_loans_usd_millions'), 1)}, "
            f"d_cash={_fmt_number(row.get('d_cash_assets_usd_millions'), 1)}"
        )
    return lines


def _sample_warning(sample_summary: pd.DataFrame) -> str:
    if sample_summary.empty:
        return "No sample summary was available; do not interpret response differences."
    common = sample_summary.loc[
        (sample_summary["sample"] == "common_target_periods")
        & (sample_summary["bank_group"] == "all_target_groups")
    ]
    if common.empty:
        return "No common target-group sample is available; do not interpret response differences."
    row = common.iloc[0]
    coupon_rows = int(row.get("coupon_heavy_rows", 0))
    context_share = float(row.get("context_complete_share", 0.0))
    warnings = []
    if coupon_rows < 12:
        warnings.append(
            f"Coupon-heavy support is too thin in the common target-group sample "
            f"({coupon_rows} rows), so bill-versus-coupon contrasts are not stable."
        )
    if context_share < 0.75:
        warnings.append(
            f"Context completeness is {context_share:.2f}, below the full-go threshold; "
            "TGA-complete diagnostics should be read as a later-sample screen."
        )
    if not warnings:
        warnings.append("Common target-group coverage is adequate for a scoped mechanism memo.")
    return " ".join(warnings)


def write_mechanism_memo(
    *,
    panel_path: str | Path,
    diagnostics_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """Write a guarded H.8 mechanism-screen memo from generated diagnostics."""

    panel = read_csv(panel_path)
    diag = Path(diagnostics_dir)
    sample_summary = read_csv(diag / "sample_summary.csv") if (diag / "sample_summary.csv").exists() else pd.DataFrame()
    response = (
        read_csv(diag / "bank_group_response_table.csv")
        if (diag / "bank_group_response_table.csv").exists()
        else pd.DataFrame()
    )
    common_response = (
        read_csv(diag / "common_target_response_table.csv")
        if (diag / "common_target_response_table.csv").exists()
        else pd.DataFrame()
    )
    tga_response = (
        read_csv(diag / "tga_complete_response_table.csv")
        if (diag / "tga_complete_response_table.csv").exists()
        else pd.DataFrame()
    )
    common_relative_response = (
        read_csv(diag / "common_target_relative_bill_share_response_table.csv")
        if (diag / "common_target_relative_bill_share_response_table.csv").exists()
        else pd.DataFrame()
    )
    tga_relative_response = (
        read_csv(diag / "tga_complete_relative_bill_share_response_table.csv")
        if (diag / "tga_complete_relative_bill_share_response_table.csv").exists()
        else pd.DataFrame()
    )
    trends = read_csv(diag / "bank_group_trends.csv") if (diag / "bank_group_trends.csv").exists() else pd.DataFrame()
    guarded = (
        read_csv(diag / "guarded_regressions.csv")
        if (diag / "guarded_regressions.csv").exists()
        else pd.DataFrame()
    )
    recommendation, reasons = _diagnostic_signal(panel)
    out = ensure_parent(output_path)

    common = _target_common_panel(panel)
    tga_complete = tga_complete_target_panel(panel)
    common_period_text = "none"
    if len(common):
        common_period_text = f"{common['period'].min()} to {common['period'].max()}"
    tga_period_text = "none"
    if len(tga_complete):
        tga_period_text = f"{tga_complete['period'].min()} to {tga_complete['period'].max()}"

    trend_lines = []
    for _, row in trends.sort_values("bank_group").iterrows() if not trends.empty else []:
        trend_lines.append(
            "- "
            f"`{row['bank_group']}`: {int(row['n_rows'])} rows, "
            f"{row['first_period']} to {row['last_period']}; "
            f"last securities/deposits={_fmt_number(row.get('last_securities_deposits_ratio'), 3)}, "
            f"last cash/deposits={_fmt_number(row.get('last_cash_deposits_ratio'), 3)}, "
            f"last loans/deposits={_fmt_number(row.get('last_loans_deposits_ratio'), 3)}"
        )

    strongest = pd.DataFrame()
    if not guarded.empty and "r_squared" in guarded.columns:
        strongest = guarded.sort_values("r_squared", ascending=False).head(6)
    guarded_lines = []
    for _, row in strongest.iterrows():
        guarded_lines.append(
            "- "
            f"`{row['bank_group']}` `{row['outcome_change']}`: "
            f"bill-share coefficient={_fmt_number(row.get('bill_share_coef'), 3)}, "
            f"R2={_fmt_number(row.get('r_squared'), 4)}, n={int(row.get('n_obs', 0))}"
        )
    if not guarded_lines:
        guarded_lines = ["- No guarded regression table is available."]

    memo = f"""# H.8 Mechanism-Screen Memo

## Bottom line

{recommendation}. {_sample_warning(sample_summary)}

## Gate checks

{chr(10).join(f"- {reason}" for reason in reasons)}
- common target-group sample: {common_period_text}

## Balance-sheet coverage

{chr(10).join(trend_lines) if trend_lines else "- No trend table is available."}

## Bill-heavy and coupon-heavy response support

Full target-group rows:

{chr(10).join(_response_lines(response))}

Common target-group sample:

{chr(10).join(_response_lines(common_response))}

TGA-complete common target-group sample ({tga_period_text}):

{chr(10).join(_response_lines(tga_response))}

## Relative high-bill and low-bill response support

These buckets compare the top and bottom configured bill-share quantiles. They are relative issuance
composition screens, not pure bill-versus-coupon regimes.

Common target-group sample:

{chr(10).join(_response_lines(common_relative_response))}

TGA-complete common target-group sample ({tga_period_text}):

{chr(10).join(_response_lines(tga_relative_response))}

## Guarded bill-share screens

{chr(10).join(guarded_lines)}

## Interpretation boundary

This memo is descriptive mechanism screening. It does not identify individual-bank absorption,
bank-level duration exposure, causal Treasury absorption, or merger-adjusted bank behavior. The H.8
securities measure is Treasury-and-agency securities. A bank-level memo should come before any Call
Report or FR Y-9C ingestion.

## Recommended next branch

1. Treat fixed-threshold coupon-heavy contrasts as unsupported under the current data.
2. Use relative high-bill and low-bill buckets as the defensible first-pass composition comparison.
3. Inspect the TGA-complete rows as a later-sample mechanism check, not a full historical result.
4. If the pattern remains stable after a defensible context definition, draft a scoped bank-level design memo;
   otherwise keep `bankcap` as an H.8 mechanism-context project.
"""
    out.write_text(memo, encoding="utf-8")
    return out
